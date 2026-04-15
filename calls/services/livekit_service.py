"""
calls/services/livekit_service.py

LiveKit operations + Cloudinary upload for recordings.

Flow:
  1. Booking confirmed → create_livekit_room() + start_room_recording()
  2. LiveKit Egress saves MP4 to local /recordings/<room_id>.mp4
  3. egress_ended webhook fires → upload_recording_to_cloudinary()
  4. Local file deleted → Cloudinary URL stored in DB
  5. Admin can access via cloudinary_secure_url (signed, time-limited)
  6. After 7 days → cleanup task deletes from Cloudinary

pip install livekit-api cloudinary
"""
import asyncio
import logging
import os
from datetime import timedelta

import cloudinary
import cloudinary.uploader
import cloudinary.utils
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────

def _lk():
    from livekit import api as lkapi
    return lkapi.LiveKitAPI(
        url=settings.LIVEKIT_URL,
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )


def _configure_cloudinary():
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )


def _run(coro):
    """Run async coroutine safely whether or not an event loop is already running."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=10)
    else:
        return asyncio.run(coro)


# ──────────────────────────────────────────────────────
# TOKEN GENERATION
# ──────────────────────────────────────────────────────

def generate_participant_token(*, room_name: str, user) -> str:
    """
    Generate LiveKit JWT for a participant.
    Frontend connects with: room.connect(sfu_url, token)
    """
    from livekit import api as lkapi

    return (
        lkapi.AccessToken(
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
        )
        .with_identity(str(user.id))
        .with_name(user.get_full_name() or user.username)
        .with_ttl(timedelta(hours=4))
        .with_grants(lkapi.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
        .to_jwt()
    )


# ──────────────────────────────────────────────────────
# ROOM MANAGEMENT
# ──────────────────────────────────────────────────────

async def _create_room(room_name: str, empty_timeout: int = 3600):
    from livekit import api as lkapi
    lk = _lk()
    try:
        return await lk.room.create_room(lkapi.CreateRoomRequest(
            name=room_name,
            empty_timeout=empty_timeout,
            max_participants=2,
        ))
    finally:
        await lk.aclose()


def create_livekit_room(room_name: str, empty_timeout: int = 3600):
    try:
        return _run(_create_room(room_name, empty_timeout=empty_timeout))
    except Exception as e:
        logger.error("create_livekit_room [%s]: %s", room_name, e)


async def _delete_room(room_name: str):
    from livekit import api as lkapi
    lk = _lk()
    try:
        await lk.room.delete_room(lkapi.DeleteRoomRequest(room=room_name))
    finally:
        await lk.aclose()


def delete_livekit_room(room_name: str):
    try:
        _run(_delete_room(room_name))
    except Exception as e:
        logger.error("delete_livekit_room [%s]: %s", room_name, e)


async def _disconnect_all(room_name: str):
    from livekit import api as lkapi
    lk = _lk()
    try:
        resp = await lk.room.list_participants(
            lkapi.ListParticipantsRequest(room=room_name)
        )
        for p in resp.participants:
            try:
                await lk.room.remove_participant(
                    lkapi.RoomParticipantIdentity(room=room_name, identity=p.identity)
                )
            except Exception as e:
                logger.warning("Could not remove %s: %s", p.identity, e)
    finally:
        await lk.aclose()


def disconnect_all_participants(room_name: str):
    try:
        _run(_disconnect_all(room_name))
    except Exception as e:
        logger.error("disconnect_all_participants [%s]: %s", room_name, e)


# ──────────────────────────────────────────────────────
# EGRESS — LOCAL FILE RECORDING
# (Cloudinary upload happens AFTER egress ends via webhook)
# ──────────────────────────────────────────────────────

async def _start_egress_local(room_name: str, local_filepath: str):
    """
    Start RoomComposite egress — saves MP4 to local /recordings/ folder.
    After egress ends, webhook triggers Cloudinary upload.
    """
    from livekit import api as lkapi
    from livekit.protocol import egress as ep

    lk = _lk()
    try:
        req = lkapi.RoomCompositeEgressRequest(
            room_name=room_name,
            layout="speaker",
            audio_only=False,
            video_only=False,
            file_outputs=[
                ep.EncodedFileOutput(
                    file_type=ep.EncodedFileType.MP4,
                    filepath=local_filepath,
                )
            ],
        )
        return await lk.egress.start_room_composite_egress(req)
    finally:
        await lk.aclose()


def start_room_recording(*, call_room) -> str | None:
    """
    Start recording for a CallRoom.
    Saves to local /recordings/<room_id>.mp4
    Returns egress_id on success.
    """
    from calls.models import CallRecording

    if not call_room.sfu_room_name:
        logger.error("start_room_recording: CallRoom %s has no sfu_room_name, skipping.", call_room.id)
        return None

    local_path = f"/recordings/{call_room.id}.mp4"

    try:
        info = _run(_start_egress_local(call_room.sfu_room_name, local_path))

        CallRecording.objects.create(
            room=call_room,
            status=CallRecording.STATUS_RECORDING,
            egress_id=info.egress_id,
            local_file_path=local_path,
        )

        logger.info("Recording started: room=%s egress=%s", call_room.id, info.egress_id)
        return info.egress_id

    except Exception as e:
        logger.error("start_room_recording [%s]: %s", call_room.id, e)
        return None


async def _stop_egress(egress_id: str):
    from livekit import api as lkapi
    lk = _lk()
    try:
        return await lk.egress.stop_egress(
            lkapi.StopEgressRequest(egress_id=egress_id)
        )
    finally:
        await lk.aclose()


def stop_room_recording(*, egress_id: str):
    from calls.models import CallRecording
    try:
        _run(_stop_egress(egress_id))
        CallRecording.objects.filter(egress_id=egress_id).update(
            ended_at=timezone.now(),
        )
        logger.info("Egress stop requested: %s", egress_id)
    except Exception as e:
        logger.error("stop_room_recording [%s]: %s", egress_id, e)


# ──────────────────────────────────────────────────────
# CLOUDINARY — UPLOAD
# ──────────────────────────────────────────────────────

def upload_recording_to_cloudinary(*, recording) -> bool:
    """
    Upload local MP4 to Cloudinary.
    Called from webhook handler after egress_ended.

    Cloudinary folder structure: qkics/recordings/<room_id>
    Type: video (not image/raw) so Cloudinary can stream it

    Returns True on success, False on failure.
    """
    from calls.models import CallRecording

    local_path = recording.local_file_path

    if not local_path or not os.path.exists(local_path):
        logger.error(
            "Local file not found for recording %s: %s",
            recording.id, local_path,
        )
        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_FAILED,
        )
        return False

    try:
        _configure_cloudinary()

        # Update status to UPLOADING
        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_UPLOADING,
        )

        # Upload to Cloudinary
        public_id = f"qkics/recordings/{recording.room_id}"

        result = cloudinary.uploader.upload(
            local_path,
            resource_type="video",
            public_id=public_id,
            overwrite=True,
            # Private so direct URL doesn't work without signature
            type="private",
            # Tags for easy management
            tags=["call_recording", str(recording.room_id)],
        )

        file_size = os.path.getsize(local_path)

        # Update DB with Cloudinary info
        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_READY,
            cloudinary_public_id=result["public_id"],
            cloudinary_secure_url=result["secure_url"],
            file_size_bytes=file_size,
            duration_seconds=int(result.get("duration", 0)) or None,
        )

        logger.info(
            "Cloudinary upload complete: recording=%s public_id=%s",
            recording.id, result["public_id"],
        )

        # Delete local file after successful upload
        os.remove(local_path)
        CallRecording.objects.filter(id=recording.id).update(
            local_file_path="",
        )
        logger.info("Local file deleted: %s", local_path)

        return True

    except Exception as e:
        logger.error("Cloudinary upload failed [%s]: %s", recording.id, e)
        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_FAILED,
        )
        return False


# ──────────────────────────────────────────────────────
# CLOUDINARY — SIGNED URL FOR ADMIN DOWNLOAD
# ──────────────────────────────────────────────────────

def generate_cloudinary_signed_url(*, public_id: str, expires_in: int = 3600) -> str | None:
    """
    Generate a time-limited signed URL for admin to download recording.
    URL expires after expires_in seconds (default 1 hour).
    File stays private — only this URL works temporarily.
    """
    try:
        _configure_cloudinary()

        # Generate signed URL for private video
        url = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type="video",
            type="private",
            sign_url=True,
            expires_at=int(timezone.now().timestamp()) + expires_in,
            attachment=True,   # forces download instead of stream
        )[0]

        return url

    except Exception as e:
        logger.error("Cloudinary signed URL failed [%s]: %s", public_id, e)
        return None


def delete_cloudinary_recording(*, public_id: str) -> bool:
    """
    Delete recording from Cloudinary.
    Called by 7-day cleanup task.
    """
    try:
        _configure_cloudinary()
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type="video",
            type="private",
        )
        success = result.get("result") == "ok"
        if success:
            logger.info("Cloudinary deleted: %s", public_id)
        else:
            logger.warning("Cloudinary delete returned: %s for %s", result, public_id)
        return success
    except Exception as e:
        logger.error("Cloudinary delete failed [%s]: %s", public_id, e)
        return False


# ──────────────────────────────────────────────────────
# WEBHOOK HANDLER
# ──────────────────────────────────────────────────────

def handle_livekit_webhook(raw_body: bytes, auth_header: str):
    """
    Handle LiveKit webhook events.

    egress_ended  → upload local MP4 to Cloudinary (in background thread)
    room_finished → mark CallRoom ENDED, stop active recordings
    """
    from livekit import api as lkapi
    from calls.models import CallRoom, CallRecording

    verifier = lkapi.TokenVerifier(
        api_key=settings.LIVEKIT_API_KEY,
        api_secret=settings.LIVEKIT_API_SECRET,
    )
    receiver = lkapi.WebhookReceiver(verifier)

    try:
        event = receiver.receive(raw_body.decode(), auth_header)
    except Exception as e:
        logger.warning("Webhook verification failed: %s", e)
        return None

    event_name = event.event

    # ── Recording finished → upload to Cloudinary ──
    if event_name == "egress_ended":
        ei = event.egress_info

        # ei.status is a protobuf int enum; EGRESS_COMPLETE = 3
        try:
            from livekit.protocol import egress as _ep
            _EGRESS_COMPLETE = _ep.EGRESS_COMPLETE
        except AttributeError:
            _EGRESS_COMPLETE = 3  # fallback: EgressStatus.EGRESS_COMPLETE

        if ei.status == _EGRESS_COMPLETE:
            # Run Cloudinary upload in background thread (non-blocking)
            import threading
            try:
                recording = CallRecording.objects.get(egress_id=ei.egress_id)

                def upload_in_background():
                    upload_recording_to_cloudinary(recording=recording)

                t = threading.Thread(target=upload_in_background, daemon=True)
                t.start()
                logger.info("Cloudinary upload started in background: egress=%s", ei.egress_id)

            except CallRecording.DoesNotExist:
                logger.warning("No CallRecording found for egress_id=%s", ei.egress_id)

        else:
            # Egress failed/aborted
            CallRecording.objects.filter(egress_id=ei.egress_id).update(
                status=CallRecording.STATUS_FAILED,
                ended_at=timezone.now(),
            )
            logger.error("Egress failed: id=%s status=%s", ei.egress_id, ei.status)

    # ── First participant joins → start recording + mark ACTIVE ──
    elif event_name == "participant_joined":
        room_name = event.room.name
        try:
            call_room = CallRoom.objects.get(sfu_room_name=room_name)

            # Mark ACTIVE on first join
            if call_room.status == CallRoom.STATUS_WAITING:
                CallRoom.objects.filter(id=call_room.id).update(
                    status=CallRoom.STATUS_ACTIVE,
                    started_at=timezone.now(),
                )
                logger.info("CallRoom ACTIVE: room=%s", room_name)

            # Start recording only once (no duplicate egress)
            if not CallRecording.objects.filter(room=call_room).exists():
                import threading
                def _start_rec():
                    start_room_recording(call_room=call_room)
                threading.Thread(target=_start_rec, daemon=True).start()
                logger.info("Recording triggered: first participant joined room=%s", room_name)

        except CallRoom.DoesNotExist:
            logger.warning("participant_joined: no CallRoom for sfu_room_name=%s", room_name)
        except Exception as e:
            logger.error("participant_joined handler [%s]: %s", room_name, e)

    # ── Room closed → mark ended only if the slot time has passed ──
    elif event_name == "room_finished":
        room_name = event.room.name
        now = timezone.now()

        try:
            call_room = CallRoom.objects.get(sfu_room_name=room_name)
        except CallRoom.DoesNotExist:
            logger.warning("room_finished: no CallRoom for sfu_room_name=%s", room_name)
            return event_name

        # If the scheduled slot is still active, do NOT mark as ENDED.
        # Participants may have temporarily disconnected; they can rejoin
        # and LiveKit will auto-create the room (auto_create: true in config).
        if call_room.scheduled_end and now < call_room.scheduled_end:
            logger.info(
                "room_finished before slot end (scheduled_end=%s): %s — skipping ENDED",
                call_room.scheduled_end, room_name,
            )
            return event_name

        # Slot has ended (or no scheduled_end) → mark ENDED and stop recordings
        if call_room.status != CallRoom.STATUS_ENDED:
            CallRoom.objects.filter(id=call_room.id).update(
                status=CallRoom.STATUS_ENDED,
                ended_at=now,
            )
            for rec in CallRecording.objects.filter(
                room=call_room,
                status=CallRecording.STATUS_RECORDING,
            ):
                stop_room_recording(egress_id=rec.egress_id)

        logger.info("room_finished: %s ended", room_name)

    return event_name
