import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from adminpanel.pagination import AdminPagination
from meetings.models import Meeting, MeetingInvite
from meetings.serializers import (
    AdminMeetingCreateSerializer,
    AdminMeetingSerializer,
    AdminMeetingUpdateSerializer,
    MeetingInviteCreateSerializer,
    MeetingInviteSerializer,
    PublicMeetingSerializer,
)
from meetings.services import meeting_service
from users.permissions import IsAdmin

logger = logging.getLogger(__name__)
User = get_user_model()


def _annotated_meetings():
    return Meeting.objects.select_related("host", "call_room").annotate(
        invited_count_annotated=Count("invites", distinct=True),
        joined_count_annotated=Count(
            "invites", filter=Q(invites__joined_at__isnull=False), distinct=True
        ),
    )


# ─────────────────────────────────────────────
# ADMIN
# ─────────────────────────────────────────────

class AdminMeetingListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/meetings/admin/          list meetings
    POST /api/v1/meetings/admin/          create a meeting + its call room
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "access_mode", "host"]
    search_fields = ["title", "description", "host__username"]
    ordering_fields = ["created_at", "scheduled_start", "status", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return _annotated_meetings()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminMeetingCreateSerializer
        return AdminMeetingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        meeting = serializer.save(host=request.user)
        meeting_service.provision_call_room(meeting)
        return Response(
            AdminMeetingSerializer(meeting, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AdminMeetingDetailView(APIView):
    """
    GET    /api/v1/meetings/admin/<uuid:meeting_id>/
    PATCH  /api/v1/meetings/admin/<uuid:meeting_id>/
    DELETE /api/v1/meetings/admin/<uuid:meeting_id>/   (cancel, not hard delete)
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def _get(self, meeting_id):
        return _annotated_meetings().filter(id=meeting_id).first()

    def get(self, request, meeting_id):
        meeting = self._get(meeting_id)
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            AdminMeetingSerializer(meeting, context={"request": request}).data
        )

    def patch(self, request, meeting_id):
        meeting = self._get(meeting_id)
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if meeting.status in (Meeting.STATUS_ENDED, Meeting.STATUS_CANCELLED):
            return Response(
                {"detail": f"A {meeting.status.lower()} meeting cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AdminMeetingUpdateSerializer(
            meeting, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        meeting = serializer.save()

        # Keep the backing room's schedule in step (auto-cut reads these).
        if meeting.call_room:
            room = meeting.call_room
            room.scheduled_start = meeting.scheduled_start
            room.scheduled_end = meeting.scheduled_end
            room.save(update_fields=["scheduled_start", "scheduled_end", "updated_at"])

        return Response(
            AdminMeetingSerializer(meeting, context={"request": request}).data
        )

    def delete(self, request, meeting_id):
        """Cancel the meeting — the link stops working, the record is kept."""
        meeting = self._get(meeting_id)
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if meeting.status == Meeting.STATUS_CANCELLED:
            return Response(
                {"detail": "Already cancelled."}, status=status.HTTP_400_BAD_REQUEST
            )

        if meeting.status == Meeting.STATUS_LIVE:
            meeting_service.end_meeting(meeting)

        meeting.status = Meeting.STATUS_CANCELLED
        meeting.save(update_fields=["status", "updated_at"])
        return Response(
            AdminMeetingSerializer(meeting, context={"request": request}).data
        )


class AdminMeetingEndView(APIView):
    """POST /api/v1/meetings/admin/<uuid:meeting_id>/end/"""

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, meeting_id):
        meeting = Meeting.objects.select_related("call_room").filter(
            id=meeting_id
        ).first()
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if meeting.status == Meeting.STATUS_ENDED:
            return Response(
                {"detail": "Already ended."}, status=status.HTTP_400_BAD_REQUEST
            )

        meeting_service.end_meeting(meeting)
        return Response(
            AdminMeetingSerializer(meeting, context={"request": request}).data
        )


class AdminMeetingRegenerateLinkView(APIView):
    """POST /api/v1/meetings/admin/<uuid:meeting_id>/regenerate-link/

    Issues a new token; anyone holding the old link is locked out at once.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request, meeting_id):
        meeting = Meeting.objects.filter(id=meeting_id).first()
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not meeting.is_open:
            return Response(
                {"detail": "This meeting is no longer open."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        meeting.rotate_invite_token()
        return Response(
            AdminMeetingSerializer(meeting, context={"request": request}).data
        )


class AdminMeetingInvitesView(APIView):
    """
    GET  /api/v1/meetings/admin/<uuid:meeting_id>/invites/
    POST /api/v1/meetings/admin/<uuid:meeting_id>/invites/
         {"user_ids": [1,2], "emails": ["a@b.com"], "send_email": true}
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, meeting_id):
        meeting = Meeting.objects.filter(id=meeting_id).first()
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        invites = meeting.invites.select_related("user")
        return Response(MeetingInviteSerializer(invites, many=True).data)

    def post(self, request, meeting_id):
        meeting = Meeting.objects.select_related("host").filter(id=meeting_id).first()
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not meeting.is_open:
            return Response(
                {"detail": "This meeting is no longer open."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = MeetingInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_ids = serializer.validated_data["user_ids"]
        emails = serializer.validated_data["emails"]
        send_email = serializer.validated_data["send_email"]

        from meetings.services.invites import notify_invited_user, send_invite_email

        link = meeting_service.build_invite_link(meeting, request)
        created, skipped = [], []

        for user in User.objects.filter(id__in=user_ids):
            invite, is_new = MeetingInvite.objects.get_or_create(
                meeting=meeting, user=user
            )
            if not is_new:
                skipped.append(user.username)
                continue
            created.append(invite)
            notify_invited_user(user=user, meeting=meeting, link=link)
            if send_email and user.email:
                send_invite_email(
                    to=user.email,
                    meeting=meeting,
                    link=link,
                    invitee_name=user.get_full_name() or user.username,
                )

        for email in emails:
            if meeting.invites.filter(email__iexact=email, user__isnull=True).exists():
                skipped.append(email)
                continue
            invite = MeetingInvite.objects.create(meeting=meeting, email=email)
            created.append(invite)
            if send_email:
                send_invite_email(to=email, meeting=meeting, link=link)

        return Response(
            {
                "invited": MeetingInviteSerializer(created, many=True).data,
                "skipped": skipped,
                "invite_link": link,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AdminMeetingInviteDeleteView(APIView):
    """DELETE /api/v1/meetings/admin/<uuid:meeting_id>/invites/<int:invite_id>/"""

    permission_classes = [IsAuthenticated, IsAdmin]

    def delete(self, request, meeting_id, invite_id):
        deleted, _ = MeetingInvite.objects.filter(
            meeting_id=meeting_id, id=invite_id
        ).delete()
        if not deleted:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminMeetingAttendanceView(APIView):
    """
    GET /api/v1/meetings/admin/<uuid:meeting_id>/attendance/

    Who actually joined the LiveKit room, from CallParticipant.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request, meeting_id):
        meeting = Meeting.objects.select_related("call_room").filter(
            id=meeting_id
        ).first()
        if not meeting:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not meeting.call_room_id:
            return Response({"attendees": [], "recordings": []})

        from calls.models import CallParticipant, CallRecording

        rows = (
            CallParticipant.objects.filter(room_id=meeting.call_room_id)
            .select_related("user", "guest")
            .order_by("joined_at")
        )
        attendees = [
            {
                "user_id": p.user_id,
                "username": p.user.username if p.user_id else None,
                "full_name": p.display_name,
                "is_guest": p.guest_id is not None,
                "is_host": p.user_id is not None and p.user_id == meeting.host_id,
                "joined_at": p.joined_at,
                "left_at": p.left_at,
                "duration_seconds": p.duration_seconds,
            }
            for p in rows
        ]

        recordings = [
            {
                "id": str(r.id),
                "status": r.status,
                "started_at": r.started_at,
                "ended_at": r.ended_at,
                "duration_seconds": r.duration_seconds,
                "file_size_bytes": r.file_size_bytes,
                "delete_after": r.delete_after,
            }
            for r in CallRecording.objects.filter(
                room_id=meeting.call_room_id
            ).order_by("-started_at")
        ]

        return Response({"attendees": attendees, "recordings": recordings})


# ─────────────────────────────────────────────
# PUBLIC (link holders)
# ─────────────────────────────────────────────

class PublicMeetingDetailView(APIView):
    """
    GET /api/v1/meetings/<token>/

    Pre-join metadata. Auth optional: an anonymous caller still sees the title
    and time so the page can explain what they are being asked to sign in for —
    except for INVITED_ONLY meetings, which reveal nothing without a login.
    """

    permission_classes = [AllowAny]

    def get(self, request, token):
        meeting = Meeting.objects.select_related("host").filter(
            invite_token=token
        ).first()
        if not meeting:
            return Response(
                {"detail": "This meeting link is invalid."},
                status=status.HTTP_404_NOT_FOUND,
            )

        anonymous = not request.user or not request.user.is_authenticated

        if anonymous and meeting.access_mode == Meeting.INVITED_ONLY:
            return Response(
                {
                    "requires_login": True,
                    "requires_invite": True,
                    "detail": "Sign in to see this meeting.",
                },
                status=status.HTTP_200_OK,
            )

        data = PublicMeetingSerializer(meeting, context={"request": request}).data
        data["requires_login"] = anonymous

        if not anonymous:
            allowed, reason = meeting_service.can_user_join(meeting, request.user)
            data["can_join"] = allowed
            data["reason"] = reason
            data["is_host"] = request.user.id == meeting.host_id
        else:
            allowed, reason, blocker = meeting_service.can_guest_join(meeting)
            data["can_join"] = allowed
            data["reason"] = reason or ""
            data["is_host"] = False
            # The page asks for a name when guests are welcome, shows a sign-in
            # button only when signing in would actually get them in.
            data["needs_name"] = allowed
            data["requires_login"] = (
                blocker == meeting_service.GUEST_BLOCKED_NEEDS_LOGIN
            )

        return Response(data)


class PublicMeetingJoinView(APIView):
    """
    POST /api/v1/meetings/<token>/join/

    Two ways in:
      • signed-in user  → body {} ; access decided by the meeting's access mode
      • guest (no account) → body {"display_name": "Asha"} ; only when the
        meeting is ANYONE_WITH_LINK and allow_guests is on

    Returns the room id + a LiveKit token so the client can connect. Guests also
    get a `guest_token` for the in-call chat socket.
    """

    permission_classes = [AllowAny]

    def post(self, request, token):
        meeting = Meeting.objects.select_related("host", "call_room").filter(
            invite_token=token
        ).first()
        if not meeting:
            return Response(
                {"detail": "This meeting link is invalid."},
                status=status.HTTP_404_NOT_FOUND,
            )

        is_authed = bool(request.user and request.user.is_authenticated)

        if is_authed:
            allowed, reason = meeting_service.can_user_join(meeting, request.user)
            if not allowed:
                return Response({"detail": reason}, status=status.HTTP_403_FORBIDDEN)
        else:
            allowed, reason, blocker = meeting_service.can_guest_join(meeting)
            if not allowed:
                return Response(
                    {
                        "detail": reason,
                        "requires_login": blocker
                        == meeting_service.GUEST_BLOCKED_NEEDS_LOGIN,
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        guest = None
        guest_token = None
        if not is_authed:
            from meetings.services.guest_auth import (
                clean_display_name,
                issue_guest_token,
            )
            from meetings.models import MeetingGuest

            display_name = clean_display_name(request.data.get("display_name", ""))
            if len(display_name) < 2:
                return Response(
                    {"display_name": ["Please enter your name (at least 2 characters)."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            guest = MeetingGuest.objects.create(
                meeting=meeting, display_name=display_name
            )
            guest_token = issue_guest_token(guest)

        room = meeting.call_room or meeting_service.provision_call_room(meeting)

        # A room closed by a previous "end" is reopened while the link is valid,
        # mirroring CallRoomDetailView's rejoin behaviour.
        from calls.models import CallRoom

        if room.status == CallRoom.STATUS_ENDED:
            CallRoom.objects.filter(id=room.id).update(
                status=CallRoom.STATUS_WAITING, ended_at=None
            )
            room.status = CallRoom.STATUS_WAITING

        if is_authed:
            meeting_service.mark_joined(meeting, request.user)
        elif meeting.status == Meeting.STATUS_SCHEDULED and not meeting.require_host:
            meeting.status = Meeting.STATUS_LIVE
            meeting.save(update_fields=["status", "updated_at"])

        try:
            from calls.services.livekit_service import (
                build_participant_token,
                generate_participant_token,
            )

            if is_authed:
                livekit_token = generate_participant_token(
                    room_name=room.sfu_room_name, user=request.user
                )
                display_name = request.user.get_full_name() or request.user.username
                identity = str(request.user.id)
            else:
                identity = guest.livekit_identity
                display_name = guest.display_name
                livekit_token = build_participant_token(
                    room_name=room.sfu_room_name,
                    identity=identity,
                    display_name=display_name,
                )
        except Exception as e:
            logger.error("LiveKit token failed [meeting=%s]: %s", meeting.id, e)
            return Response(
                {"detail": "Could not create a media token. Please retry."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "room_id": str(room.id),
                "meeting_id": str(meeting.id),
                "title": meeting.title,
                "livekit_token": livekit_token,
                "livekit_url": settings.LIVEKIT_PUBLIC_URL,
                "identity": identity,
                "display_name": display_name,
                "is_host": is_authed and request.user.id == meeting.host_id,
                "is_guest": not is_authed,
                "guest_token": guest_token,
                "is_recorded": True,
                "scheduled_end": meeting.scheduled_end,
            }
        )


class MyMeetingsView(generics.ListAPIView):
    """
    GET /api/v1/meetings/my/

    Meetings the signed-in user hosts or was invited to, still open.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = PublicMeetingSerializer

    def get_queryset(self):
        user = self.request.user
        return (
            Meeting.objects.select_related("host")
            .filter(
                Q(host=user) | Q(invites__user=user),
                status__in=[Meeting.STATUS_SCHEDULED, Meeting.STATUS_LIVE],
            )
            .distinct()
            .order_by("scheduled_start", "created_at")
        )

    def list(self, request, *args, **kwargs):
        rows = self.get_queryset()
        data = []
        for meeting in rows:
            if meeting.is_expired:
                continue
            item = PublicMeetingSerializer(meeting, context={"request": request}).data
            item["invite_token"] = meeting.invite_token
            item["is_host"] = meeting.host_id == request.user.id
            data.append(item)
        return Response(data)
