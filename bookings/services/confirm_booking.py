from django.db import transaction
from django.utils import timezone
from bookings.models import Booking, ExpertSlot
from payments.models import Payment


def confirm_booking_after_payment(*, payment: Payment):
    """
    Called after payment SUCCESS.
    """

    if payment.status != Payment.STATUS_SUCCESS:
        return

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(uuid=payment.reference_id)

        if booking.status != Booking.STATUS_PAYMENT_IN_PROGRESS:
            return

        slot = booking.slot

        booking.status = Booking.STATUS_CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.save(update_fields=["status", "confirmed_at"])

        slot.status = ExpertSlot.STATUS_BOOKED
        slot.save(update_fields=["status"])
