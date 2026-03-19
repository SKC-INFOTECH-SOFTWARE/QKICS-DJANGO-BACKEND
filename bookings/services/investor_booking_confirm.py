from django.db import transaction
from bookings.models import InvestorBooking
from chat.services.create_room import get_or_create_chat_room
from notifications.services.events import (
    notify_investor_booking_created,
    notify_investor_booking_confirmed,
)


@transaction.atomic
def create_investor_booking(*, user, slot):

    # create chat room
    chat_room = get_or_create_chat_room(
        user=user,
        advisor=slot.investor,
    )

    # create booking
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

    return booking
