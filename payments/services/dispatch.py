"""
Gateway-neutral post-payment fulfilment.

When ANY gateway reports a payment as SUCCESS, this routes it to the right
domain action based on `purpose`. Kept separate from gateways so the same
fulfilment runs whether the money came through Fake, PayU, or a future one.

Idempotent: safe to call more than once (each domain confirm re-checks state).
"""

from payments.models import Payment


def fulfill_payment(payment: Payment):
    if payment.status != Payment.STATUS_SUCCESS:
        return

    if payment.purpose == Payment.PURPOSE_BOOKING:
        from bookings.services.confirm_booking import confirm_booking_after_payment
        confirm_booking_after_payment(payment=payment)

    elif payment.purpose == Payment.PURPOSE_SUBSCRIPTION:
        from subscriptions.services.activate import activate_subscription_after_payment
        activate_subscription_after_payment(payment=payment)

    # DOCUMENT / COMPANY_POST purposes can be wired here later.
