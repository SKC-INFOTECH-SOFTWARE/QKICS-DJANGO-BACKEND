from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models import JSONField
from datetime import timedelta


class SubscriptionPlan(models.Model):
    """
    Premium subscription plans.
    Example:
    - 1 month  → ₹199
    - 3 months → ₹299
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    duration_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Duration of the plan in days"
    )

    price = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Price in INR"
    )

    features = JSONField(
        default=dict,
        blank=True,
        help_text="Flexible JSON to store benefits (max_docs, free_consult, chats etc.)"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - ₹{self.price}"

    class Meta:
        ordering = ["price"]


class UserSubscription(models.Model):
    """
    Tracks a user's current and past subscriptions.
    Only one subscription should be active at a time.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name="user_subscriptions"
    )

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()

    is_active = models.BooleanField(default=True)

    # Razorpay or payment system reference
    payment_reference = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Order or transaction ID"
    )

    # Usage tracking (resets monthly)
    monthly_doc_download_count = models.PositiveIntegerField(default=0)
    free_consult_used = models.BooleanField(default=False)
    monthly_chat_used = models.PositiveIntegerField(default=0)

    renewal_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    # ---------------------------------------------------------
    # Utility methods
    # ---------------------------------------------------------

    def is_expired(self):
        return timezone.now() > self.end_date

    def remaining_days(self):
        delta = self.end_date - timezone.now()
        return max(delta.days, 0)

    def reset_monthly_usage(self):
        """Call this function at start of each month via cron/celery."""
        self.monthly_doc_download_count = 0
        self.monthly_chat_used = 0
        self.free_consult_used = False
        self.save(update_fields=[
            "monthly_doc_download_count",
            "monthly_chat_used",
            "free_consult_used"
        ])

    def extend_subscription(self, extra_days):
        """Extend an active subscription OR expired one."""
        if self.is_expired():
            self.start_date = timezone.now()
            self.end_date = timezone.now() + timedelta(days=extra_days)
        else:
            self.end_date += timedelta(days=extra_days)

        self.renewal_count += 1
        self.save()

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({'Active' if self.is_active else 'Expired'})"

    class Meta:
        ordering = ["-created_at"]
