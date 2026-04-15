from django.utils import timezone

from calls.models import CallRoom
from calls.services.auto_cut import schedule_auto_cut
from calls.services.livekit_service import create_livekit_room

# Extra buffer added on top of slot duration so LiveKit keeps the room
# open even if participants join a little late or reconnect near the end.
_BUFFER_SECONDS = 600  # 10 minutes


def _slot_empty_timeout(end_datetime) -> int:
    """
    Compute empty_timeout (seconds) for LiveKit room creation.
    = seconds until slot ends + 10-min buffer, minimum 600 s.
    """
    if end_datetime:
        remaining = int((end_datetime - timezone.now()).total_seconds())
        return max(remaining + _BUFFER_SECONDS, _BUFFER_SECONDS)
    return 3600  # fallback: 1 hour


def create_call_room_for_booking(*, booking):
    """
    Create CallRoom for an expert Booking.
    DB record is saved first — LiveKit call is non-critical.
    """
    print("🔥 CALL ROOM FUNCTION HIT", booking.uuid)
    try:
        return booking.call_room
    except Exception:
        pass

    room_name = f"booking_{booking.uuid}"

    call_room = CallRoom.objects.create(
        booking=booking,
        user=booking.user,
        advisor=booking.expert,
        scheduled_start=booking.start_datetime,
        scheduled_end=booking.end_datetime,
        sfu_room_name=room_name,
    )

    create_livekit_room(room_name, empty_timeout=_slot_empty_timeout(booking.end_datetime))
    schedule_auto_cut(call_room=call_room)

    return call_room


def create_call_room_for_investor_booking(*, investor_booking):
    """
    Create CallRoom for an InvestorBooking.
    DB record is saved first — LiveKit call is non-critical.
    """
    try:
        return investor_booking.call_room
    except Exception:
        pass

    room_name = f"investor_booking_{investor_booking.uuid}"

    call_room = CallRoom.objects.create(
        investor_booking=investor_booking,
        user=investor_booking.user,
        advisor=investor_booking.investor,
        scheduled_start=investor_booking.start_datetime,
        scheduled_end=investor_booking.end_datetime,
        sfu_room_name=room_name,
    )

    create_livekit_room(room_name, empty_timeout=_slot_empty_timeout(investor_booking.end_datetime))
    schedule_auto_cut(call_room=call_room)

    return call_room
