import logging

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        from apscheduler.schedulers.background import BackgroundScheduler
        from django_apscheduler.jobstores import DjangoJobStore

        _scheduler = BackgroundScheduler(timezone="UTC")
        _scheduler.add_jobstore(DjangoJobStore(), "default")

        if not _scheduler.running:
            _scheduler.start()
            logger.info("APScheduler started.")

    return _scheduler


def schedule_auto_cut(*, call_room):
    from django.utils import timezone

    if not call_room.scheduled_end:
        return

    if call_room.scheduled_end <= timezone.now():
        return

    job_id = f"auto_cut_{call_room.id}"

    try:
        scheduler = get_scheduler()
        run_at    = call_room.scheduled_end.replace(tzinfo=None)  # naive UTC

        scheduler.add_job(
            _auto_cut_job,
            trigger="date",
            run_date=run_at,
            id=job_id,
            name=f"Auto-cut CallRoom {call_room.id}",
            args=[str(call_room.id)],
            replace_existing=True,
            misfire_grace_time=120,
        )

        from calls.models import CallRoom
        CallRoom.objects.filter(id=call_room.id).update(auto_cut_scheduled=True)

        logger.info("Auto-cut scheduled: room=%s at=%s", call_room.id, call_room.scheduled_end)

    except Exception as e:
        logger.error("schedule_auto_cut [%s]: %s", call_room.id, e)


def _auto_cut_job(room_id: str):
    logger.info("AUTO-CUT firing: room=%s", room_id)

    try:
        from calls.models import CallRoom, CallRecording
        from django.utils import timezone

        room = CallRoom.objects.get(id=room_id)

        if room.status == CallRoom.STATUS_ENDED:
            return

        # 1. Disconnect all LiveKit participants
        if room.sfu_room_name:
            try:
                from calls.services.livekit_service import disconnect_all_participants
                disconnect_all_participants(room.sfu_room_name)
            except Exception as e:
                logger.error("disconnect_all_participants: %s", e)

        # 2. Stop active recordings
        for rec in CallRecording.objects.filter(room=room, status=CallRecording.STATUS_RECORDING):
            try:
                from calls.services.livekit_service import stop_room_recording
                stop_room_recording(egress_id=rec.egress_id)
            except Exception as e:
                logger.error("stop_room_recording: %s", e)

        # 3. Mark ENDED
        room.status   = CallRoom.STATUS_ENDED
        room.ended_at = timezone.now()
        room.save(update_fields=["status", "ended_at", "updated_at"])

        # 4. Delete LiveKit room
        try:
            from calls.services.livekit_service import delete_livekit_room
            delete_livekit_room(room.sfu_room_name)
        except Exception:
            pass

        logger.info("Auto-cut complete: room=%s", room_id)

    except Exception as e:
        logger.error("_auto_cut_job [%s]: %s", room_id, e)


def cancel_auto_cut(*, room_id: str):
    try:
        get_scheduler().remove_job(f"auto_cut_{room_id}")
    except Exception:
        pass
