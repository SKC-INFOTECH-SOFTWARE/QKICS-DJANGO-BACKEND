"""
calls/services/livekit_service.py

LiveKit operations + LOCAL recording storage.

Flow:
  1. Booking confirmed → create_livekit_room() + start_room_recording()
  2. LiveKit Egress saves MP4 to local /recordings/<room_id>.mp4 (Docker volume)
  3. egress_ended webhook fires → finalize_recording() (file stays on the volume)
  4. Admin previews/downloads via a short-lived signed token → Django streams the
     local file (see calls/views.py AdminCallRecording* views)
  5. After RETENTION_DAYS (15) → cleanup task deletes the local file

Recordings are NOT uploaded to Cloudinary anymore — the MP4 lives on the mounted
`/recordings` volume, shared between the egress and backend containers.

pip install livekit-api
"""
import asyncio
import logging
import os
import threading
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from rplatform.locks import distributed_lock

logger = logging.getLogger(__name__)

# Salt for the short-lived signed tokens that authorise a recording download.
_RECORDING_TOKEN_SALT = "calls.recording.download.v1"


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
# RECORDING AUDIT TRAIL + ADMIN ALERTS
# ──────────────────────────────────────────────────────

_FAILURE_EVENTS = {"EGRESS_START_FAILED", "EGRESS_FAILED", "UPLOAD_FAILED"}


def _log_event(event, *, room=None, recording=None, detail=""):
    """Append a RecordingEvent row (audit trail) and mirror it to the logs.
    Never raises — auditing must not break the pipeline."""
    detail = (detail or "")[:2000]
    try:
        from calls.models import RecordingEvent
        RecordingEvent.objects.create(
            room=room, recording=recording, event=event, detail=detail,
        )
    except Exception:
        logger.exception("Failed to write RecordingEvent %s", event)

    log = logger.error if event in _FAILURE_EVENTS else logger.info
    log("[recording] %s room=%s rec=%s %s", event,
        getattr(room, "id", None), getattr(recording, "id", None), detail)


def _alert_recording_failed(call_room, detail):
    """Best-effort admin alert on a recording failure. Swallows all errors."""
    try:
        from notifications.services.events import notify_admins_recording_failed
        label = getattr(call_room, "sfu_room_name", None) or f"room {getattr(call_room, 'id', '?')}"
        notify_admins_recording_failed(
            room_label=label, detail=detail, room_id=getattr(call_room, "id", None),
        )
    except Exception:
        logger.exception("Failed to alert admins about recording failure")


def ensure_recording_started(call_room, trigger=""):
    """
    Idempotently mark the room ACTIVE and start recording if it isn't already.

    Safe to call from multiple webhook events — recording now starts on BOTH
    `room_started` AND `participant_joined`, so a single dropped event can no
    longer leave a call unrecorded. The exists()-check plus the distributed lock
    dedupe concurrent triggers down to one egress.
    """
    from calls.models import CallRoom, CallRecording

    if call_room.status == CallRoom.STATUS_WAITING:
        CallRoom.objects.filter(id=call_room.id).update(
            status=CallRoom.STATUS_ACTIVE, started_at=timezone.now(),
        )
        logger.info("CallRoom ACTIVE: room=%s (%s)", call_room.sfu_room_name, trigger)

    if CallRecording.objects.filter(room=call_room).exists():
        return

    def _work():
        with distributed_lock(f"egress:start:{call_room.id}", ttl=60) as got:
            if not got:
                return  # another worker is already starting it
            if CallRecording.objects.filter(room=call_room).exists():
                return  # started by the worker that held the lock first
            start_room_recording(call_room=call_room, trigger=trigger)

    threading.Thread(target=_work, daemon=True).start()


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

async def _create_room(room_name: str, empty_timeout: int = 3600, max_participants: int = 2):
    from livekit import api as lkapi
    lk = _lk()
    try:
        return await lk.room.create_room(lkapi.CreateRoomRequest(
            name=room_name,
            empty_timeout=empty_timeout,
            max_participants=max_participants,
        ))
    finally:
        await lk.aclose()


def create_livekit_room(room_name: str, empty_timeout: int = 3600, max_participants: int = 2):
    try:
        return _run(_create_room(
            room_name,
            empty_timeout=empty_timeout,
            max_participants=max_participants,
        ))
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


async def _mute_participant_mic(room_name: str, identity: str):
    """Server-side force-mute of a participant's microphone track(s)."""
    from livekit import api as lkapi
    from livekit.protocol import models as lkm

    lk = _lk()
    try:
        participant = await lk.room.get_participant(
            lkapi.RoomParticipantIdentity(room=room_name, identity=identity)
        )
        muted_any = False
        for pub in participant.tracks:
            is_mic = (
                pub.source == lkm.TrackSource.MICROPHONE
                or pub.type == lkm.TrackType.AUDIO
            )
            if is_mic and not pub.muted:
                await lk.room.mute_published_track(
                    lkapi.MutePublishedTrackRequest(
                        room=room_name,
                        identity=identity,
                        track_sid=pub.sid,
                        muted=True,
                    )
                )
                muted_any = True
        return muted_any
    finally:
        await lk.aclose()


def mute_participant_mic(room_name: str, identity: str) -> bool:
    """Force-mute a participant's mic. Used by the host (expert) in group calls."""
    try:
        return bool(_run(_mute_participant_mic(room_name, identity)))
    except Exception as e:
        logger.error("mute_participant_mic [%s/%s]: %s", room_name, identity, e)
        return False


async def _mute_all_mics(room_name: str, except_identity: str | None):
    """Force-mute every participant's mic except `except_identity` (the host)."""
    from livekit import api as lkapi
    from livekit.protocol import models as lkm

    lk = _lk()
    try:
        resp = await lk.room.list_participants(
            lkapi.ListParticipantsRequest(room=room_name)
        )
        count = 0
        for p in resp.participants:
            if except_identity and p.identity == except_identity:
                continue
            for pub in p.tracks:
                is_mic = (
                    pub.source == lkm.TrackSource.MICROPHONE
                    or pub.type == lkm.TrackType.AUDIO
                )
                if is_mic and not pub.muted:
                    await lk.room.mute_published_track(
                        lkapi.MutePublishedTrackRequest(
                            room=room_name,
                            identity=p.identity,
                            track_sid=pub.sid,
                            muted=True,
                        )
                    )
                    count += 1
        return count
    finally:
        await lk.aclose()


def mute_all_participants(room_name: str, except_identity: str | None = None) -> int:
    """Mute everyone's mic (host stays unmuted). Returns number of tracks muted."""
    try:
        return int(_run(_mute_all_mics(room_name, except_identity)))
    except Exception as e:
        logger.error("mute_all_participants [%s]: %s", room_name, e)
        return 0


async def _remove_participant(room_name: str, identity: str):
    from livekit import api as lkapi

    lk = _lk()
    try:
        await lk.room.remove_participant(
            lkapi.RoomParticipantIdentity(room=room_name, identity=identity)
        )
    finally:
        await lk.aclose()


def remove_participant(room_name: str, identity: str) -> bool:
    """Disconnect a participant from the live call. Used by the host."""
    try:
        _run(_remove_participant(room_name, identity))
        return True
    except Exception as e:
        logger.error("remove_participant [%s/%s]: %s", room_name, identity, e)
        return False


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
            # ── Encode profile (4-core server) ───────────────────────────────
            # Server ab 4-core hai + egress ko ~2 core budget diya gaya hai
            # (livekit/egress.yaml room_composite_cpu_cost=2.0), to 720p @ 30fps
            # comfortably chalega. File local volume par 15 din rehti hai, isliye
            # bitrate ~2500 kbps par capped rakha hai (≈1.1 GB/ghanta) taaki disk
            # controlled rahe. Agar wapas 2-core par jaao to 480p/24fps + cpu_cost
            # 1.5 kar dena.
            advanced=ep.EncodingOptions(
                width=1280,
                height=720,
                framerate=30,
                video_bitrate=2500,   # kbps
                audio_bitrate=128,    # kbps
                key_frame_interval=4,
            ),
        )
        return await lk.egress.start_room_composite_egress(req)
    finally:
        await lk.aclose()


def start_room_recording(*, call_room, trigger="") -> str | None:
    """
    Start recording for a CallRoom.
    Saves to local /recordings/<room_id>.mp4
    Returns egress_id on success.
    """
    from calls.models import CallRecording, RecordingEvent

    if not call_room.sfu_room_name:
        logger.error("start_room_recording: CallRoom %s has no sfu_room_name, skipping.", call_room.id)
        _log_event(RecordingEvent.EGRESS_START_FAILED, room=call_room,
                   detail="CallRoom has no sfu_room_name")
        _alert_recording_failed(call_room, "room has no sfu_room_name")
        return None

    local_path = f"/recordings/{call_room.id}.mp4"

    try:
        info = _run(_start_egress_local(call_room.sfu_room_name, local_path))

        recording = CallRecording.objects.create(
            room=call_room,
            status=CallRecording.STATUS_RECORDING,
            egress_id=info.egress_id,
            local_file_path=local_path,
        )

        logger.info("Recording started: room=%s egress=%s", call_room.id, info.egress_id)
        _log_event(RecordingEvent.EGRESS_STARTED, room=call_room, recording=recording,
                   detail=f"egress={info.egress_id} trigger={trigger}")
        return info.egress_id

    except Exception as e:
        logger.error("start_room_recording [%s]: %s", call_room.id, e)
        _log_event(RecordingEvent.EGRESS_START_FAILED, room=call_room, detail=str(e))
        _alert_recording_failed(call_room, f"egress start failed: {e}")
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
# LOCAL RECORDING — FINALIZE (after egress ends)
# ──────────────────────────────────────────────────────

def finalize_recording(*, recording, duration_seconds: int | None = None) -> bool:
    """
    Finalize a recording once egress has ended.

    The MP4 already sits on the shared /recordings volume, so there is nothing to
    upload — we just verify the file exists, record its size/duration and flip the
    status to READY. The file stays on disk until the retention cleanup runs.

    Returns True on success, False if the file is missing.
    """
    from calls.models import CallRecording, RecordingEvent

    local_path = recording.local_file_path

    if not local_path or not os.path.exists(local_path):
        msg = f"local file not found: {local_path}"
        logger.error("Local file not found for recording %s: %s", recording.id, local_path)
        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_FAILED,
            error_message=msg[:500],
        )
        _log_event(RecordingEvent.UPLOAD_FAILED, room=recording.room, recording=recording, detail=msg)
        _alert_recording_failed(recording.room, msg)
        return False

    try:
        file_size = os.path.getsize(local_path)

        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_READY,
            file_size_bytes=file_size,
            duration_seconds=duration_seconds or None,
        )

        logger.info(
            "Recording finalized (local): recording=%s file=%s size=%s",
            recording.id, local_path, file_size,
        )
        _log_event(RecordingEvent.UPLOAD_COMPLETE, room=recording.room, recording=recording,
                   detail=f"local file={local_path} size={file_size}")
        return True

    except Exception as e:
        logger.error("finalize_recording failed [%s]: %s", recording.id, e)
        CallRecording.objects.filter(id=recording.id).update(
            status=CallRecording.STATUS_FAILED,
            error_message=str(e)[:500],
        )
        _log_event(RecordingEvent.UPLOAD_FAILED, room=recording.room, recording=recording, detail=str(e))
        _alert_recording_failed(recording.room, f"finalize failed: {e}")
        return False


# ──────────────────────────────────────────────────────
# SIGNED DOWNLOAD TOKENS (admin preview/download of local files)
# ──────────────────────────────────────────────────────

def make_recording_download_token(*, recording_id, expires_in: int = 3600) -> str:
    """
    Short-lived signed token authorising a download of one recording.

    Embedded in the stream URL as `?token=` so a plain <video src> / new-tab
    download works without an Authorization header, while the file stays private
    (the stream view rejects anything without a valid, unexpired token).
    """
    exp = int(timezone.now().timestamp()) + int(expires_in)
    return signing.dumps(
        {"rid": str(recording_id), "exp": exp},
        salt=_RECORDING_TOKEN_SALT,
    )


def verify_recording_download_token(token: str) -> str | None:
    """Return the recording id if the token is valid and unexpired, else None."""
    try:
        data = signing.loads(token, salt=_RECORDING_TOKEN_SALT)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict):
        return None
    if int(data.get("exp", 0)) < int(timezone.now().timestamp()):
        return None
    return data.get("rid")


def delete_local_recording(*, recording) -> bool:
    """
    Delete a recording's MP4 from the local /recordings volume.
    Called by the retention cleanup task.
    """
    local_path = recording.local_file_path
    if not local_path:
        return True
    try:
        if os.path.exists(local_path):
            os.remove(local_path)
            logger.info("Local recording deleted: %s", local_path)
        return True
    except Exception as e:
        logger.error("delete_local_recording failed [%s]: %s", recording.id, e)
        return False


# ──────────────────────────────────────────────────────
# WEBHOOK HANDLER
# ──────────────────────────────────────────────────────

def handle_livekit_webhook(raw_body: bytes, auth_header: str):
    """
    Handle LiveKit webhook events.

    egress_ended  → finalize local MP4 (mark READY; file stays on the volume)
    room_finished → mark CallRoom ENDED, stop active recordings
    """
    from livekit import api as lkapi
    from calls.models import CallRoom, CallRecording, RecordingEvent

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

                # A duplicate egress_ended that arrives AFTER a successful upload
                # (local file already deleted, status READY) must NOT re-run the
                # upload — it would find no local file and wrongly mark a good
                # recording FAILED. Only upload if still RECORDING.
                if recording.status != CallRecording.STATUS_RECORDING:
                    logger.info(
                        "egress_ended for %s but recording status=%s — skipping duplicate upload",
                        ei.egress_id, recording.status,
                    )
                    return event_name

                _log_event(RecordingEvent.EGRESS_ENDED, room=recording.room, recording=recording,
                           detail=f"egress={ei.egress_id}")

                # Duration comes from the egress file result (nanoseconds).
                duration_seconds = None
                try:
                    results = list(getattr(ei, "file_results", None) or [])
                    if not results and getattr(ei, "file", None):
                        results = [ei.file]
                    if results and getattr(results[0], "duration", 0):
                        duration_seconds = int(results[0].duration / 1_000_000_000)
                except Exception:
                    duration_seconds = None

                def finalize_in_background():
                    # Serialise concurrent deliveries: only one worker finalizes.
                    with distributed_lock(f"egress:finalize:{ei.egress_id}", ttl=120) as got:
                        if not got:
                            logger.info(
                                "egress finalize already in progress for %s — skipping duplicate",
                                ei.egress_id,
                            )
                            return
                        finalize_recording(recording=recording, duration_seconds=duration_seconds)

                t = threading.Thread(target=finalize_in_background, daemon=True)
                t.start()
                logger.info("Recording finalize started in background: egress=%s", ei.egress_id)

            except CallRecording.DoesNotExist:
                logger.warning("No CallRecording found for egress_id=%s", ei.egress_id)

        else:
            # Egress failed/aborted
            CallRecording.objects.filter(egress_id=ei.egress_id).update(
                status=CallRecording.STATUS_FAILED,
                ended_at=timezone.now(),
                error_message=f"egress ended with status={ei.status}"[:500],
            )
            logger.error("Egress failed: id=%s status=%s", ei.egress_id, ei.status)
            rec = CallRecording.objects.filter(egress_id=ei.egress_id).select_related("room").first()
            _log_event(RecordingEvent.EGRESS_FAILED, room=getattr(rec, "room", None), recording=rec,
                       detail=f"egress={ei.egress_id} status={ei.status}")
            if rec:
                _alert_recording_failed(rec.room, f"egress failed (status={ei.status})")

    # ── Room starts OR first participant joins → ensure recording is running ──
    # Recording now triggers on BOTH events so a single dropped webhook can't
    # leave a call unrecorded. ensure_recording_started() is idempotent.
    elif event_name in ("room_started", "participant_joined"):
        room_name = event.room.name
        try:
            call_room = CallRoom.objects.get(sfu_room_name=room_name)
            ensure_recording_started(call_room, trigger=event_name)
        except CallRoom.DoesNotExist:
            logger.warning("%s: no CallRoom for sfu_room_name=%s", event_name, room_name)
        except Exception as e:
            logger.error("%s handler [%s]: %s", event_name, room_name, e)

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
