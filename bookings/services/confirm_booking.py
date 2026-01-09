import uuid
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment
from chat.services.create_room import get_or_create_chat_room


def confirm_booking_after_payment(*, payment: Payment):
    """
    Called after payment SUCCESS.
    Creates chat room and confirms booking.
    """

    if payment.status != Payment.STATUS_SUCCESS:
        return

    if payment.purpose != Payment.PURPOSE_BOOKING:
        return

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(
            uuid=payment.reference_id
        )

        # Only valid flow
        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            return

        # STEP 1: mark paid
        booking.status = Booking.STATUS_PAID
        booking.paid_at = timezone.now()

        # STEP 2: confirm booking
        booking.status = Booking.STATUS_CONFIRMED
        booking.confirmed_at = timezone.now()

        # STEP 3: create chat room
        chat_room = get_or_create_chat_room(
            user=booking.user,
            expert=booking.expert,
        )

        # store room id for quick lookup
        booking.chat_room_id = chat_room.id

        booking.save(
            update_fields=[
                "status",
                "paid_at",
                "confirmed_at",
                "chat_room_id",
                "updated_at",
            ]
        )
