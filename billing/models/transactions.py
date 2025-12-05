# billing/models/transactions.py

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import JSONField

from .orders import PaymentOrder


TRANSACTION_STATUS_CHOICES = [
    ("success", "Success"),
    ("failed", "Failed"),
    ("pending", "Pending"),
]


class PaymentTransaction(models.Model):
    """
    Stores actual payment attempts and results.
    A PaymentOrder may have 1-N transactions (retries).
    """

    order = models.ForeignKey(
        PaymentOrder,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_transactions"
    )

    # Razorpay payment reference
    razorpay_payment_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    razorpay_signature = models.CharField(
        max_length=255, null=True, blank=True
    )

    # Payment details
    amount = models.PositiveIntegerField(
        help_text="Amount paid (in paise)"
    )
    currency = models.CharField(max_length=20, default="INR")

    status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default="pending"
    )

    # Raw webhook / payment payload from Razorpay
    raw_response = JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["razorpay_payment_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Txn {self.id} | Order {self.order_id} | {self.status}"

    # -----------------------------------------------------
    # STATUS HELPERS
    # -----------------------------------------------------
    def mark_success(self, raw_data=None):
        """Mark transaction as successful and update order."""
        self.status = "success"
        self.processed_at = timezone.now()

        if raw_data:
            self.raw_response = raw_data

        self.save(update_fields=["status", "processed_at", "raw_response"])

        # Update parent order
        self.order.mark_paid(transaction=self)

    def mark_failed(self, raw_data=None, reason=None):
        """Mark transaction as failed."""
        self.status = "failed"
        self.processed_at = timezone.now()

        if raw_data:
            self.raw_response = raw_data

        if reason:
            self.raw_response.setdefault("failure_reason", reason)

        self.save(update_fields=["status", "processed_at", "raw_response"])

        # Update order but do NOT mark it expired (user may retry)
        self.order.mark_failed(reason=reason)

    def is_success(self):
        return self.status == "success"

    def is_failed(self):
        return self.status == "failed"

    def is_pending(self):
        return self.status == "pending"
