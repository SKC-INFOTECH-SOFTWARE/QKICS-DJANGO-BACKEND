from django.db import transaction
from django.utils import timezone

from bookings.models import InvestorBooking
from chat.services.create_room import get_or_create_chat_room


def confirm_investor_booking(*, booking: InvestorBooking):

    with transaction.atomic():

        if booking.status != InvestorBooking.STATUS_PENDING:
            return

        # confirm booking
        booking.status = InvestorBooking.STATUS_CONFIRMED
        booking.save(update_fields=["status", "updated_at"])

        # create chat room
        chat_room = get_or_create_chat_room(
            user=booking.user,
            investor=booking.investor,
        )

        booking.chat_room_id = chat_room.id
        booking.save(update_fields=["chat_room_id"])
