from calls.models import CallRoom
from calls.services.auto_cut import schedule_auto_cut
from calls.services.livekit_service import create_livekit_room


def create_call_room_for_booking(*, booking):
    """
    Central place to create CallRoom.
    """
    if hasattr(booking, "call_room") and booking.call_room:
        return booking.call_room

    room_name = f"booking_{booking.uuid}"

    call_room = CallRoom.objects.create(
        booking=booking,
        user=booking.user,
        advisor=booking.expert,
        scheduled_start=booking.start_datetime,
        scheduled_end=booking.end_datetime,
        sfu_room_name=room_name,
    )

    # LiveKit room creation is non-critical — DB record already saved above
    create_livekit_room(room_name)

    schedule_auto_cut(call_room=call_room)

    return call_room
