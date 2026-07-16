"""
Activate a UserSubscription after its payment succeeds.

Extracted from the view so both the instant (fake) flow and the async
(PayU callback) flow reuse the exact same activation logic. Idempotent.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from payments.models import Payment
from subscriptions.models import SubscriptionPlan, UserSubscription
from notifications.services.events import notify_subscription_activated


def activate_subscription_after_payment(*, payment: Payment):
    if payment.status != Payment.STATUS_SUCCESS:
        return None
    if payment.purpose != Payment.PURPOSE_SUBSCRIPTION:
        return None

    with transaction.atomic():
        # Guard against double activation from webhook + redirect racing.
        existing = (
            UserSubscription.objects.select_for_update()
            .filter(user=payment.user, is_active=True, end_date__gt=timezone.now())
            .first()
        )
        if existing:
            return existing

        try:
            plan = SubscriptionPlan.objects.get(uuid=payment.reference_id)
        except SubscriptionPlan.DoesNotExist:
            return None

        start_date = timezone.now()
        end_date = start_date + timedelta(days=plan.duration_days)

        subscription = UserSubscription.objects.create(
            user=payment.user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )

    notify_subscription_activated(subscription)
    return subscription
