import uuid
from django.db import models
from django.conf import settings
from django.db import models
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class SubscriptionPlan(models.Model):
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    name = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField()

    price = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Price in INR"
    )

    # Limits / benefits
    premium_doc_limit_per_month = models.PositiveIntegerField(default=5)
    free_consultation_count = models.PositiveIntegerField(default=1)
    free_chat_per_month = models.PositiveIntegerField(default=3)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["price"]

    def __str__(self):
        return f"{self.name} ({self.duration_days} days)"


class UserSubscription(models.Model):
    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="subscriptions"
    )

    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.PROTECT, related_name="user_subscriptions"
    )

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    # Usage tracking
    premium_docs_used_this_month = models.PositiveIntegerField(default=0)
    chats_used_this_month = models.PositiveIntegerField(default=0)
    free_consultation_used = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["end_date"]),
        ]

    def __str__(self):
        return f"{self.user} → {self.plan.name}"

    def is_valid(self):
        return (
            self.is_active
            and self.start_date <= timezone.now()
            and self.end_date > timezone.now()
        )
