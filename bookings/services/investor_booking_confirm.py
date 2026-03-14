from django.db import transaction
from bookings.models import InvestorBooking
from chat.services.create_room import get_or_create_chat_room


@transaction.atomic
def create_investor_booking(*, user, slot):

    # create chat room
    chat_room = get_or_create_chat_room(
        user=user,
        investor=slot.investor,
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

    return booking
