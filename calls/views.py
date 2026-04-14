import logging

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CallRoom, CallMessage, CallNote, CallRecording
from .serializers import (
    CallRoomSerializer,
    CallMessageSerializer,
    CallNoteSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HELPER — get room or 404, enforce access
# ─────────────────────────────────────────────

def _get_room_for_user(room_id, user):
    """Return CallRoom if the user is a participant, else None."""
    try:
        room = CallRoom.objects.get(id=room_id)
    except CallRoom.DoesNotExist:
        return None
    if room.user_id != user.id and room.advisor_id != user.id:
        return None
    return room


# ─────────────────────────────────────────────
# USER-FACING VIEWS
# ─────────────────────────────────────────────

class MyCallRoomsView(generics.ListAPIView):
    """
    GET /api/v1/calls/my/
    Returns all CallRooms where the authenticated user is either
    the user or the advisor, newest first.
    """
    serializer_class   = CallRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return (
            CallRoom.objects
            .filter(Q(user=user) | Q(advisor=user))
            .order_by("-created_at")
        )


class MyCallNotesView(generics.ListAPIView):
    """
    GET /api/v1/calls/notes/my/
    Returns all private notes written by the authenticated user.
    """
    serializer_class   = CallNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            CallNote.objects
            .filter(user=self.request.user)
            .select_related("room")
            .order_by("-updated_at")
        )


class CallRoomDetailView(APIView):
    """
    GET /api/v1/calls/<uuid:room_id>/
    Returns room detail + a LiveKit access token so the client can join.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = _get_room_for_user(room_id, request.user)
        if room is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        data = CallRoomSerializer(room, context={"request": request}).data

        # Generate LiveKit token
        try:
            from livekit import api as lkapi

            grant = lkapi.VideoGrants(
                room_join=True,
                room=room.sfu_room_name,
                can_publish=True,
                can_subscribe=True,
            )
            token = (
                lkapi.AccessToken(
                    api_key=settings.LIVEKIT_API_KEY,
                    api_secret=settings.LIVEKIT_API_SECRET,
                )
                .with_identity(str(request.user.id))
                .with_name(request.user.get_full_name() or request.user.username)
                .with_grants(grant)
                .to_jwt()
            )
            data["livekit_token"] = token
            data["livekit_url"]   = settings.LIVEKIT_PUBLIC_URL
        except Exception as e:
            logger.error("LiveKit token generation failed [room=%s]: %s", room_id, e)
            data["livekit_token"] = None
            data["livekit_url"]   = None

        return Response(data)


class EndCallView(APIView):
    """
    POST /api/v1/calls/<uuid:room_id>/end/
    Marks the call as ENDED. Either participant can end the call.
    Also stops any active recordings.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = _get_room_for_user(room_id, request.user)
        if room is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.status == CallRoom.STATUS_ENDED:
            return Response({"detail": "Call already ended."}, status=status.HTTP_400_BAD_REQUEST)

        # Stop active recordings
        for rec in room.recordings.filter(status=CallRecording.STATUS_RECORDING):
            try:
                from calls.services.livekit_service import stop_room_recording
                stop_room_recording(egress_id=rec.egress_id)
            except Exception as e:
                logger.error("stop_room_recording on EndCallView [%s]: %s", rec.egress_id, e)

        # Disconnect all LiveKit participants
        if room.sfu_room_name:
            try:
                from calls.services.livekit_service import disconnect_all_participants
                disconnect_all_participants(room.sfu_room_name)
            except Exception as e:
                logger.error("disconnect_all_participants [%s]: %s", room_id, e)

        room.status   = CallRoom.STATUS_ENDED
        room.ended_at = timezone.now()
        room.save(update_fields=["status", "ended_at", "updated_at"])

        return Response({"detail": "Call ended."}, status=status.HTTP_200_OK)


class CallMessageListView(generics.ListAPIView):
    """
    GET /api/v1/calls/<uuid:room_id>/messages/
    Returns all chat messages for a call room.
    """
    serializer_class   = CallMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        room = _get_room_for_user(self.kwargs["room_id"], self.request.user)
        if room is None:
            return CallMessage.objects.none()
        return room.call_messages.select_related("sender").order_by("created_at")


class CallFileUploadView(APIView):
    """
    POST /api/v1/calls/<uuid:room_id>/upload/
    Upload a file during a call. Saves a CallMessage with the file attached.
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request, room_id):
        room = _get_room_for_user(room_id, request.user)
        if room is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.status == CallRoom.STATUS_ENDED:
            return Response(
                {"detail": "Cannot upload to an ended call."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = request.FILES.get("file")
        if not file:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 50 MB limit
        if file.size > 50 * 1024 * 1024:
            return Response(
                {"detail": "File exceeds 50 MB limit."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        message = CallMessage.objects.create(
            room=room,
            sender=request.user,
            file=file,
            file_name=file.name,
            file_size_bytes=file.size,
        )

        return Response(
            CallMessageSerializer(message, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class CallNoteView(APIView):
    """
    GET  /api/v1/calls/<uuid:room_id>/notes/  → retrieve own note
    POST /api/v1/calls/<uuid:room_id>/notes/  → create or update own note
    """
    permission_classes = [IsAuthenticated]

    def _get_room(self, room_id, user):
        return _get_room_for_user(room_id, user)

    def get(self, request, room_id):
        room = self._get_room(room_id, request.user)
        if room is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        note = CallNote.objects.filter(room=room, user=request.user).first()
        if note is None:
            return Response({"content": ""}, status=status.HTTP_200_OK)

        return Response(CallNoteSerializer(note, context={"request": request}).data)

    def post(self, request, room_id):
        room = self._get_room(room_id, request.user)
        if room is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        content = request.data.get("content", "")

        note, created = CallNote.objects.update_or_create(
            room=room,
            user=request.user,
            defaults={"content": content},
        )

        return Response(
            CallNoteSerializer(note, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────
# LIVEKIT WEBHOOK
# ─────────────────────────────────────────────

class LiveKitWebhookView(APIView):
    """
    POST /api/v1/calls/livekit/webhook/
    Receives events from LiveKit server (egress_ended, room_finished, etc.).
    No JWT auth — verified via LiveKit signature.
    """
    authentication_classes = []
    permission_classes     = []

    def post(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        raw_body    = request.body

        try:
            from calls.services.livekit_service import handle_livekit_webhook
            event_name = handle_livekit_webhook(
                raw_body=raw_body,
                auth_header=auth_header,
            )
            if event_name is None:
                return Response(
                    {"detail": "Webhook verification failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"event": event_name}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("LiveKitWebhookView error: %s", e)
            return Response(
                {"detail": "Internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ─────────────────────────────────────────────
# ADMIN VIEWS
# ─────────────────────────────────────────────

class AdminCallRecordingListView(generics.ListAPIView):
    """
    GET /api/v1/calls/admin/recordings/
    Admin: list all recordings (excluding deleted).
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        recordings = (
            CallRecording.objects
            .exclude(status=CallRecording.STATUS_DELETED)
            .select_related("room__user", "room__advisor")
            .order_by("-started_at")
        )

        data = [
            {
                "id":                    str(r.id),
                "room_id":               str(r.room_id),
                "participants":          f"{r.room.user.username if r.room.user else 'deleted'} ↔ {r.room.advisor.username if r.room.advisor else 'deleted'}",
                "status":                r.status,
                "cloudinary_public_id":  r.cloudinary_public_id,
                "file_size_mb":          round(r.file_size_bytes / 1024 / 1024, 2) if r.file_size_bytes else None,
                "duration_seconds":      r.duration_seconds,
                "started_at":            r.started_at,
                "ended_at":              r.ended_at,
                "delete_after":          r.delete_after,
            }
            for r in recordings
        ]

        return Response(data)


class AdminCallRecordingSignedUrlView(APIView):
    """
    GET /api/v1/calls/admin/recordings/<uuid:recording_id>/signed-url/
    Admin: generate a time-limited Cloudinary signed URL for download.
    """
    permission_classes = [IsAdminUser]

    def get(self, request, recording_id):
        try:
            recording = CallRecording.objects.get(
                id=recording_id,
                status=CallRecording.STATUS_READY,
            )
        except CallRecording.DoesNotExist:
            return Response({"detail": "Recording not found or not ready."}, status=status.HTTP_404_NOT_FOUND)

        if not recording.cloudinary_public_id:
            return Response(
                {"detail": "No Cloudinary asset linked to this recording."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from calls.services.livekit_service import generate_cloudinary_signed_url

            expires_in = int(request.query_params.get("expires_in", 3600))
            url = generate_cloudinary_signed_url(
                public_id=recording.cloudinary_public_id,
                expires_in=expires_in,
            )

            if url is None:
                return Response(
                    {"detail": "Failed to generate signed URL."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response({"signed_url": url, "expires_in": expires_in})

        except Exception as e:
            logger.error("AdminCallRecordingSignedUrlView [%s]: %s", recording_id, e)
            return Response(
                {"detail": "Internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )