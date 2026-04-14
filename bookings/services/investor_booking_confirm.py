from django.db import transaction
from bookings.models import InvestorBooking
from chat.services.create_room import get_or_create_chat_room
from notifications.services.events import (
    notify_investor_booking_created,
    notify_investor_booking_confirmed,
)


@transaction.atomic
def create_investor_booking(*, user, slot):
    chat_room = get_or_create_chat_room(user=user, advisor=slot.investor)

    booking = InvestorBooking.objects.create(
        user=user,
        investor=slot.investor,
        slot=slot,
        start_datetime=slot.start_datetime,
        end_datetime=slot.end_datetime,
        duration_minutes=slot.duration_minutes,
        status=InvestorBooking.STATUS_CONFIRMED,
        chat_room_id=chat_room.id,
    )
    notify_investor_booking_created(booking)
    notify_investor_booking_confirmed(booking)

    try:
        from calls.services.call_room_service import (
            create_call_room_for_investor_booking,
        )

        create_call_room_for_investor_booking(investor_booking=booking)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "CallRoom creation failed for investor booking %s", booking.uuid
        )

    return booking
