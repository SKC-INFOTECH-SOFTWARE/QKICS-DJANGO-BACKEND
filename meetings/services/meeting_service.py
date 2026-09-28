"""
Meeting lifecycle: provisioning the backing CallRoom + LiveKit room, resolving
who may join, and ending a meeting.

All LiveKit/recording behaviour is the existing `calls` machinery — this module
only wires a Meeting to a CallRoom.
"""
import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


def provision_call_room(meeting):
    """Create the CallRoom + LiveKit room for `meeting` (idempotent).

    Recording is NOT started here: LiveKit webhooks start it when the first
    participant joins, exactly as for bookings and batch slots.
    """
    from calls.models import CallRoom

    if meeting.call_room_id:
        return meeting.call_room

    with transaction.atomic():
        room = CallRoom.objects.create(
            advisor=meeting.host,
            status=CallRoom.STATUS_WAITING,
            sfu_room_name=f"meeting_{meeting.id}",
            scheduled_start=meeting.scheduled_start,
            scheduled_end=meeting.scheduled_end,
        )
        meeting.call_room = room
        meeting.save(update_fields=["call_room", "updated_at"])

    # LiveKit auto-creates rooms on first join, so a failure here is not fatal —
    # it only means we could not pre-set max_participants.
    try:
        from calls.services.livekit_service import create_livekit_room

        create_livekit_room(
            room_name=room.sfu_room_name,
            max_participants=meeting.max_participants + 1,  # +1 for the host
        )
    except Exception as e:
        logger.error("create_livekit_room failed [meeting=%s]: %s", meeting.id, e)

    return room


def can_user_join(meeting, user):
    """(allowed: bool, reason: str) for `user` joining `meeting` right now."""
    from meetings.models import Meeting, MeetingInvite

    if meeting.status == Meeting.STATUS_CANCELLED:
        return False, "This meeting has been cancelled."
    if meeting.status == Meeting.STATUS_ENDED:
        return False, "This meeting has ended."
    if meeting.is_expired:
        return False, "This meeting link has expired."

    is_host = user.id == meeting.host_id

    if not is_host and not meeting.can_join_now():
        opens = meeting.join_opens_at()
        if opens:
            return False, f"This meeting opens at {opens.isoformat()}."
        return False, "This meeting is not open yet."

    if is_host:
        return True, ""

    if meeting.access_mode == Meeting.INVITED_ONLY:
        invited = MeetingInvite.objects.filter(
            meeting=meeting, user_id=user.id
        ).exists()
        if not invited:
            return False, "You are not on the invite list for this meeting."

    if meeting.require_host and meeting.status != Meeting.STATUS_LIVE:
        return False, "Waiting for the host to start the meeting."

    return True, ""


# Returned as the third element of can_guest_join() so callers can tell
# "sign in and you're through" apart from "wait, or the meeting is over".
GUEST_BLOCKED_NEEDS_LOGIN = "NEEDS_LOGIN"
GUEST_BLOCKED_OTHER = "OTHER"


def can_guest_join(meeting):
    """(allowed, reason, blocker) for someone WITHOUT a Qkics account.

    `blocker` is GUEST_BLOCKED_NEEDS_LOGIN only when signing in would actually
    let them in — the pre-join page uses it to decide between showing a name
    field, a sign-in button, or a plain message.
    """
    from meetings.models import Meeting

    if meeting.status == Meeting.STATUS_CANCELLED:
        return False, "This meeting has been cancelled.", GUEST_BLOCKED_OTHER
    if meeting.status == Meeting.STATUS_ENDED:
        return False, "This meeting has ended.", GUEST_BLOCKED_OTHER
    if meeting.is_expired:
        return False, "This meeting link has expired.", GUEST_BLOCKED_OTHER

    if meeting.access_mode == Meeting.INVITED_ONLY or not meeting.allow_guests:
        return (
            False,
            "Sign in with your Qkics account to join this meeting.",
            GUEST_BLOCKED_NEEDS_LOGIN,
        )

    if not meeting.can_join_now():
        opens = meeting.join_opens_at()
        if opens:
            return False, f"This meeting opens at {opens.isoformat()}.", GUEST_BLOCKED_OTHER
        return False, "This meeting is not open yet.", GUEST_BLOCKED_OTHER

    if meeting.require_host and meeting.status != Meeting.STATUS_LIVE:
        return False, "Waiting for the host to start the meeting.", GUEST_BLOCKED_OTHER

    return True, "", ""


def mark_joined(meeting, user):
    """Record the join: flip the meeting LIVE and stamp the invite."""
    from meetings.models import Meeting, MeetingInvite

    updates = []
    if meeting.host_id == user.id and meeting.status == Meeting.STATUS_SCHEDULED:
        meeting.status = Meeting.STATUS_LIVE
        updates.append("status")
    elif meeting.status == Meeting.STATUS_SCHEDULED and not meeting.require_host:
        meeting.status = Meeting.STATUS_LIVE
        updates.append("status")

    if updates:
        meeting.save(update_fields=updates + ["updated_at"])

    MeetingInvite.objects.filter(
        meeting=meeting, user_id=user.id, joined_at__isnull=True
    ).update(joined_at=timezone.now())


def end_meeting(meeting):
    """End the meeting: stop recording, disconnect everyone, close the room."""
    from calls.models import CallRecording, CallRoom
    from meetings.models import Meeting

    room = meeting.call_room

    if room:
        for rec in room.recordings.filter(status=CallRecording.STATUS_RECORDING):
            try:
                from calls.services.livekit_service import stop_room_recording

                stop_room_recording(egress_id=rec.egress_id)
            except Exception as e:
                logger.error("stop_room_recording [meeting=%s]: %s", meeting.id, e)

        if room.sfu_room_name:
            try:
                from calls.services.livekit_service import disconnect_all_participants

                disconnect_all_participants(room.sfu_room_name)
            except Exception as e:
                logger.error(
                    "disconnect_all_participants [meeting=%s]: %s", meeting.id, e
                )

        if room.status != CallRoom.STATUS_ENDED:
            room.status = CallRoom.STATUS_ENDED
            room.ended_at = timezone.now()
            room.save(update_fields=["status", "ended_at", "updated_at"])

    meeting.status = Meeting.STATUS_ENDED
    meeting.save(update_fields=["status", "updated_at"])
    return meeting


def build_invite_link(meeting, request=None):
    """Public join URL for the meeting (frontend route, not an API path)."""
    from django.conf import settings

    base = getattr(settings, "FRONTEND_URL", "") or ""
    if not base and request is not None:
        base = f"{request.scheme}://{request.get_host()}"
    return f"{base.rstrip('/')}/m/{meeting.invite_token}"
