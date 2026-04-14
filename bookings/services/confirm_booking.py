from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment
from chat.services.create_room import get_or_create_chat_room
from notifications.services.events import notify_booking_confirmed
from calls.services.call_room_service import create_call_room_for_booking

def confirm_booking_after_payment(*, payment: Payment):
    if payment.status != Payment.STATUS_SUCCESS:
        return
    if payment.purpose != Payment.PURPOSE_BOOKING:
        return

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(uuid=payment.reference_id)

        if booking.status not in (
            Booking.STATUS_PENDING,
            Booking.STATUS_AWAITING_PAYMENT,
        ):
            return

        booking.status = Booking.STATUS_CONFIRMED
        booking.paid_at = timezone.now()
        booking.confirmed_at = timezone.now()

        if not booking.expert_approved_at:
            booking.expert_approved_at = timezone.now()

        # ✅ CHAT ROOM
        chat_room = get_or_create_chat_room(
            user=booking.user,
            advisor=booking.expert
        )
        booking.chat_room_id = chat_room.id

        # ✅ CALL ROOM (MOVE INSIDE TRANSACTION)
        create_call_room_for_booking(booking=booking)

        booking.save(
            update_fields=[
                "status",
                "paid_at",
                "confirmed_at",
                "expert_approved_at",
                "chat_room_id",
                "updated_at",
            ]
        )

    notify_booking_confirmed(booking)
