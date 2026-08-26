from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from payments.models import Payment
from chat.services.create_room import get_or_create_chat_room
from notifications.services.events import notify_booking_confirmed
from calls.services.call_room_service import (
    create_call_room_for_booking,
    get_or_create_batch_call_room,
)


def _finalize_booking(booking: Booking, *, paid: bool) -> bool:
    """Transition a PENDING/AWAITING_PAYMENT booking to CONFIRMED and provision
    its chat/call room. Returns True if it actually confirmed.

    Shared by the paid path (after a successful payment) and the free path
    (no payment at all). The caller is responsible for the DB lock / atomic
    block; this only touches the given booking. `paid` just controls whether
    paid_at is stamped — free bookings leave it null.
    """
    if booking.status not in (
        Booking.STATUS_PENDING,
        Booking.STATUS_AWAITING_PAYMENT,
    ):
        return False

    now = timezone.now()
    booking.status = Booking.STATUS_CONFIRMED
    booking.confirmed_at = now
    if paid:
        booking.paid_at = now
    if not booking.expert_approved_at:
        booking.expert_approved_at = now

    if booking.is_batch:
        # Group video call: one shared CallRoom per slot (idempotent).
        get_or_create_batch_call_room(slot=booking.slot)
    elif booking.session_type == Booking.SESSION_TYPE_CHAT:
        chat_room = get_or_create_chat_room(
            user=booking.user,
            advisor=booking.expert,
        )
        booking.chat_room_id = chat_room.id
    elif booking.session_type == Booking.SESSION_TYPE_VIDEO_CALL:
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
    return True


def confirm_booking_after_payment(*, payment: Payment):
    if payment.status != Payment.STATUS_SUCCESS:
        return
    if payment.purpose != Payment.PURPOSE_BOOKING:
        return

    with transaction.atomic():
        booking = Booking.objects.select_for_update().get(uuid=payment.reference_id)
        confirmed = _finalize_booking(booking, paid=True)

    if confirmed:
        notify_booking_confirmed(booking)


def confirm_free_booking(*, booking: Booking) -> bool:
    """Confirm a zero-price booking with no payment step.

    Called for free sessions: directly at booking time (when no expert approval
    is needed) or right after the expert approves. The caller already holds a
    lock on the booking / is inside an atomic block.
    """
    confirmed = _finalize_booking(booking, paid=False)
    if confirmed:
        notify_booking_confirmed(booking)
    return confirmed
