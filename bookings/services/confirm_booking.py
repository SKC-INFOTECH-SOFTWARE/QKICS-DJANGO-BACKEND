from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment
from chat.services.create_room import get_or_create_chat_room
from notifications.services.events import notify_booking_confirmed


def confirm_booking_after_payment(*, payment: Payment):
    if payment.status != Payment.STATUS_SUCCESS:
        return
    if payment.purpose != Payment.PURPOSE_BOOKING:
        return

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(uuid=payment.reference_id)

        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            return

        booking.status       = Booking.STATUS_PAID
        booking.paid_at      = timezone.now()
        booking.status       = Booking.STATUS_CONFIRMED
        booking.confirmed_at = timezone.now()

        chat_room = get_or_create_chat_room(user=booking.user, advisor=booking.expert)
        booking.chat_room_id = chat_room.id

        booking.save(update_fields=[
            "status", "paid_at", "confirmed_at", "chat_room_id", "updated_at"
        ])

        # Video call room + recording + auto-cut (non-critical)
        try:
            from calls.services.call_room_service import create_call_room_for_booking
            create_call_room_for_booking(booking=booking)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "CallRoom creation failed for booking %s", booking.uuid
            )

        notify_booking_confirmed(booking)
