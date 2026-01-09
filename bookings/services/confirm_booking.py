# bookings/services/confirm_booking.py

from django.db import transaction
from django.utils import timezone
from bookings.models import Booking
from payments.models import Payment
import uuid


def confirm_booking_after_payment(*, payment: Payment):
    """
    Called after payment SUCCESS.
    """

    if payment.status != Payment.STATUS_SUCCESS:
        return

    if payment.purpose != Payment.PURPOSE_BOOKING:
        return

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(
            uuid=payment.reference_id
        )

        # ✅ Must be awaiting payment
        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            return

        # ✅ Step 1: mark as PAID
        booking.status = Booking.STATUS_PAID
        booking.paid_at = timezone.now()

        # ✅ Step 2: confirm booking
        booking.status = Booking.STATUS_CONFIRMED
        booking.confirmed_at = timezone.now()

        # ✅ Step 3: create chat room id
        booking.chat_room_id = uuid.uuid4()

        booking.save(
            update_fields=[
                "status",
                "paid_at",
                "confirmed_at",
                "chat_room_id",
                "updated_at",
            ]
        )
