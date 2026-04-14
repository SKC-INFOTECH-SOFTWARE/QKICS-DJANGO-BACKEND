from calls.models import CallRoom
from calls.services.auto_cut import schedule_auto_cut
from calls.services.livekit_service import create_livekit_room


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

    create_livekit_room(room_name)
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

    create_livekit_room(room_name)
    schedule_auto_cut(call_room=call_room)

    return call_room
