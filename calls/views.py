import logging
import os
import re

from django.conf import settings
from django.db.models import Q
from django.http import FileResponse, Http404, StreamingHttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
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

    # Batch (group) room: the expert (advisor) or any user with a CONFIRMED
    # booking on this slot may join.
    if room.is_batch:
        if room.advisor_id == user.id:
            return room
        from bookings.models import Booking
        has_booking = Booking.objects.filter(
            slot_id=room.slot_id,
            user_id=user.id,
            status=Booking.STATUS_CONFIRMED,
        ).exists()
        return room if has_booking else None

    # One-to-one room: only the two participants.
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
        from bookings.models import Booking
        # One-to-one rooms (user or advisor) + batch rooms the user has a
        # confirmed booking on.
        batch_slot_ids = Booking.objects.filter(
            user=user,
            is_batch=True,
            status=Booking.STATUS_CONFIRMED,
        ).values_list("slot_id", flat=True)
        return (
            CallRoom.objects
            .filter(
                Q(user=user)
                | Q(advisor=user)
                | Q(slot_id__in=batch_slot_ids)
            )
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
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # If room was marked ENDED but the slot time hasn't passed yet,
        # reset it so participants can rejoin (e.g. after a temporary disconnect).
        if room.status == CallRoom.STATUS_ENDED:
            if room.scheduled_end and timezone.now() < room.scheduled_end:
                CallRoom.objects.filter(id=room.id).update(status=CallRoom.STATUS_WAITING)
                room.status = CallRoom.STATUS_WAITING
            else:
                return Response({"message": "Call has ended."}, status=status.HTTP_403_FORBIDDEN)

        data = CallRoomSerializer(room, context={"request": request}).data

        # Generate LiveKit token
        try:
            from calls.services.livekit_service import generate_participant_token
            data["livekit_token"] = generate_participant_token(
                room_name=room.sfu_room_name,
                user=request.user,
            )
            data["livekit_url"] = settings.LIVEKIT_PUBLIC_URL
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
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.status == CallRoom.STATUS_ENDED:
            return Response({"message": "Call already ended."}, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({"message": "Call ended."}, status=status.HTTP_200_OK)


class MuteParticipantView(APIView):
    """
    POST /api/v1/calls/<uuid:room_id>/mute/
    Host (the expert/advisor) force-mutes a participant's mic in a group call.
    Body: { "identity": "<user_id>" }  (LiveKit identity == str(user.id))
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = _get_room_for_user(room_id, request.user)
        if room is None:
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Only the host (advisor) of the room may mute others.
        if room.advisor_id != request.user.id:
            return Response(
                {"message": "Only the host can mute participants."},
                status=status.HTTP_403_FORBIDDEN,
            )

        identity = str(request.data.get("identity") or "").strip()
        if not identity:
            return Response({"message": "identity is required."}, status=status.HTTP_400_BAD_REQUEST)

        if identity == str(request.user.id):
            return Response({"message": "Use the mic button to mute yourself."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calls.services.livekit_service import mute_participant_mic
            muted = mute_participant_mic(room.sfu_room_name, identity)
        except Exception as e:
            logger.error("MuteParticipantView [%s]: %s", room_id, e)
            return Response({"message": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"muted": muted}, status=status.HTTP_200_OK)


class MuteAllParticipantsView(APIView):
    """
    POST /api/v1/calls/<uuid:room_id>/mute-all/
    Host mutes everyone's mic in a group call (the host stays unmuted).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = _get_room_for_user(room_id, request.user)
        if room is None:
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if room.advisor_id != request.user.id:
            return Response(
                {"message": "Only the host can mute everyone."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            from calls.services.livekit_service import mute_all_participants
            muted = mute_all_participants(
                room.sfu_room_name, except_identity=str(request.user.id)
            )
        except Exception as e:
            logger.error("MuteAllParticipantsView [%s]: %s", room_id, e)
            return Response({"message": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"muted_count": muted}, status=status.HTTP_200_OK)


class RemoveParticipantView(APIView):
    """
    POST /api/v1/calls/<uuid:room_id>/remove/
    Host removes (disconnects) a participant from a group call.
    Body: { "identity": "<user_id>" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        room = _get_room_for_user(room_id, request.user)
        if room is None:
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if room.advisor_id != request.user.id:
            return Response(
                {"message": "Only the host can remove participants."},
                status=status.HTTP_403_FORBIDDEN,
            )

        identity = str(request.data.get("identity") or "").strip()
        if not identity:
            return Response({"message": "identity is required."}, status=status.HTTP_400_BAD_REQUEST)
        if identity == str(request.user.id):
            return Response({"message": "You cannot remove yourself."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from calls.services.livekit_service import remove_participant
            removed = remove_participant(room.sfu_room_name, identity)
        except Exception as e:
            logger.error("RemoveParticipantView [%s]: %s", room_id, e)
            return Response({"message": "Internal error."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({"removed": removed}, status=status.HTTP_200_OK)


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
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if room.status == CallRoom.STATUS_ENDED:
            return Response(
                {"message": "Cannot upload to an ended call."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        file = request.FILES.get("file")
        if not file:
            return Response({"message": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 50 MB limit
        if file.size > 50 * 1024 * 1024:
            return Response(
                {"message": "File exceeds 50 MB limit."},
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
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        note = CallNote.objects.filter(room=room, user=request.user).first()
        if note is None:
            return Response({"content": ""}, status=status.HTTP_200_OK)

        return Response(CallNoteSerializer(note, context={"request": request}).data)

    def post(self, request, room_id):
        room = self._get_room(room_id, request.user)
        if room is None:
            return Response({"message": "Not found."}, status=status.HTTP_404_NOT_FOUND)

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
                    {"message": "Webhook verification failed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"event": event_name}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error("LiveKitWebhookView error: %s", e)
            return Response(
                {"message": "Internal error."},
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
                "error_message":         r.error_message,
                "has_file":              bool(r.local_file_path),
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
    Admin: mint a short-lived signed URL that streams the LOCAL recording file.

    The URL carries a signed `?token=` so a plain <video src> / new-tab download
    works without an auth header, while the file stays private (the stream view
    rejects a missing/expired token).
    """
    permission_classes = [IsAdminUser]

    def get(self, request, recording_id):
        try:
            recording = CallRecording.objects.get(
                id=recording_id,
                status=CallRecording.STATUS_READY,
            )
        except CallRecording.DoesNotExist:
            return Response({"message": "Recording not found or not ready."}, status=status.HTTP_404_NOT_FOUND)

        if not recording.local_file_path or not os.path.exists(recording.local_file_path):
            return Response(
                {"message": "Recording file is no longer available."},
                status=status.HTTP_410_GONE,
            )

        try:
            from calls.services.livekit_service import make_recording_download_token

            expires_in = int(request.query_params.get("expires_in", 3600))
            token = make_recording_download_token(
                recording_id=recording.id, expires_in=expires_in,
            )
            path = f"/api/v1/calls/admin/recordings/{recording.id}/stream/?token={token}"
            url = request.build_absolute_uri(path)

            return Response({"signed_url": url, "expires_in": expires_in})

        except Exception as e:
            logger.error("AdminCallRecordingSignedUrlView [%s]: %s", recording_id, e)
            return Response(
                {"message": "Internal error."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Stream chunk size for range responses (1 MB).
_STREAM_CHUNK = 1024 * 1024


def _file_iterator(path, start, length, chunk_size=_STREAM_CHUNK):
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            data = f.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


class AdminCallRecordingStreamView(APIView):
    """
    GET /api/v1/calls/admin/recordings/<uuid:recording_id>/stream/?token=<signed>
    Streams the local MP4 with HTTP Range support (needed for <video> seeking).

    Auth is the signed token in the query string (minted by the signed-url view),
    NOT the JWT header — so it works from a <video src> / new browser tab. Without
    a valid, unexpired token the file is never served.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, recording_id):
        from calls.services.livekit_service import verify_recording_download_token

        token = request.query_params.get("token", "")
        rid = verify_recording_download_token(token)
        if not rid or str(rid) != str(recording_id):
            raise Http404("Invalid or expired token.")

        try:
            recording = CallRecording.objects.get(id=recording_id)
        except CallRecording.DoesNotExist:
            raise Http404("Recording not found.")

        path = recording.local_file_path
        if not path or not os.path.exists(path):
            raise Http404("Recording file is no longer available.")

        file_size = os.path.getsize(path)
        content_type = "video/mp4"
        download = request.query_params.get("download") == "1"
        filename = f"recording_{recording.room_id}.mp4"

        range_header = request.headers.get("Range", "")
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)

        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            end = min(end, file_size - 1)
            if start > end or start >= file_size:
                resp = StreamingHttpResponse(status=416)
                resp["Content-Range"] = f"bytes */{file_size}"
                return resp
            length = end - start + 1
            resp = StreamingHttpResponse(
                _file_iterator(path, start, length),
                status=206,
                content_type=content_type,
            )
            resp["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            resp["Content-Length"] = str(length)
        else:
            resp = FileResponse(open(path, "rb"), content_type=content_type)
            resp["Content-Length"] = str(file_size)

        resp["Accept-Ranges"] = "bytes"
        disposition = "attachment" if download else "inline"
        resp["Content-Disposition"] = f'{disposition}; filename="{filename}"'
        return resp