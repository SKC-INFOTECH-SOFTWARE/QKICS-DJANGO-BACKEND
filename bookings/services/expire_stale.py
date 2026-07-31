"""
Release slots held by abandoned checkouts.

When a user books a slot the booking immediately enters an ACTIVE status
(PENDING / AWAITING_PAYMENT) which blocks that slot. If the user then bails out
of the payment gateway, nothing ever moves the booking forward — the slot stays
blocked forever and the user sees a dead "Awaiting Payment" card with no way to
join and (until the frontend fix) no way to pay.

This job sweeps those stale bookings to EXPIRED (a terminal, non-blocking
status) so the slot frees up.

Timeout note: it MUST be comfortably longer than the payment gateway's own
checkout-session validity. `confirm_booking_after_payment` refuses to confirm a
booking that is no longer PENDING/AWAITING_PAYMENT, so if we expired a booking
while a genuine (slow) payment was still completing, the user could be charged
without getting the booking. 30 min is safely past PayU's checkout window.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES = 30

# Statuses that hold a slot but still await a completing action from the user.
_STALE_STATUSES = [Booking.STATUS_PENDING, Booking.STATUS_AWAITING_PAYMENT]


def _timeout_minutes() -> int:
    try:
        return int(getattr(settings, "BOOKING_PAYMENT_TIMEOUT_MINUTES", DEFAULT_TIMEOUT_MINUTES))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_MINUTES


def expire_stale_bookings() -> int:
    """
    Expire every PENDING / AWAITING_PAYMENT booking older than the timeout.
    Returns how many were expired. Idempotent and safe to run concurrently
    (each row is re-checked under a row lock before transitioning).
    """
    cutoff = timezone.now() - timedelta(minutes=_timeout_minutes())

    stale_ids = list(
        Booking.objects.filter(
            status__in=_STALE_STATUSES,
            created_at__lt=cutoff,
        ).values_list("id", flat=True)
    )

    expired = 0
    for booking_id in stale_ids:
        try:
            with transaction.atomic():
                booking = Booking.objects.select_for_update().get(id=booking_id)
                # Re-check under the lock — a payment callback may have moved it
                # to CONFIRMED between the query above and now.
                if booking.status not in _STALE_STATUSES:
                    continue
                if booking.mark_as_expired():
                    expired += 1
        except Booking.DoesNotExist:
            continue
        except Exception as e:  # never let one bad row abort the sweep
            logger.error("expire_stale_bookings [%s]: %s", booking_id, e)

    if expired:
        logger.info("expire_stale_bookings: released %s stale slot(s).", expired)
    return expired
