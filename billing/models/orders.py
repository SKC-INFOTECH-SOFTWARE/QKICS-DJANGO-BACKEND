from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import JSONField
from django.core.validators import MinValueValidator
from datetime import timedelta
import uuid


# --------------------------
# Purpose & Status constants
# --------------------------
PURPOSE_CHOICES = [
    ("premium_subscription", "Premium Subscription"),
    ("expert_consultation", "Expert Consultation (Chat)"),
    ("document_purchase", "Document Purchase"),
    ("investor_communications", "Investor Communications"),
]

ORDER_STATUS_CHOICES = [
    ("pending", "Pending"),  # order created but not paid
    ("paid", "Paid"),  # verified payment
    ("failed", "Failed"),  # payment attempt failed
    ("expired", "Expired"),  # timed out or abandoned
]


# --------------------------
# PaymentOrder
# --------------------------
class PaymentOrder(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_orders",
    )

    # purpose of the order (subscription / consultation / document / investor chat)
    purpose = models.CharField(max_length=40, choices=PURPOSE_CHOICES)

    # amount stored as integer (in paise). Use gateways' expected currency minor units.
    amount = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Amount in paise (e.g. ₹199 => 19900)",
    )
    currency = models.CharField(max_length=10, default="INR")

    # gateway order id (Razorpay order id) created before payment
    razorpay_order_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )

    # flexible metadata to attach plan id, booking id, document id etc.
    metadata = JSONField(default=dict, blank=True)

    # status lifecycle
    status = models.CharField(
        max_length=20, choices=ORDER_STATUS_CHOICES, default="pending"
    )

    # expiration handling (order should be completed within X minutes)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # optional local unique token for idempotency / client references
    client_reference = models.CharField(
        max_length=100, unique=True, default=lambda: uuid.uuid4().hex
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["razorpay_order_id"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Order {self.id} | {self.purpose} | {self.amount}/{self.currency} | {self.status}"

    # -------------------------
    # helpers & properties
    # -------------------------
    @property
    def amount_in_inr(self):
        """Return amount as float INR (for display)."""
        return self.amount / 100.0

    def is_expired(self):
        """Return whether the order is expired by time."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False

    # -------------------------
    # lifecycle methods
    # -------------------------
    def mark_paid(self, transaction=None):
        """
        Mark this order as paid.
        - `transaction` is optional PaymentTransaction instance to link or verify
        - should be called after verifying gateway signature/webhook
        """
        self.status = "paid"
        # keep metadata updated if transaction provides gateway ids
        if transaction:
            self.metadata.setdefault("payment", {})
            self.metadata["payment"].update(
                {
                    "payment_id": getattr(transaction, "gateway_payment_id", None),
                    "transaction_id": getattr(transaction, "id", None),
                }
            )
        self.save(update_fields=["status", "metadata", "updated_at"])

    def mark_failed(self, reason=None):
        """Mark order as failed. Optionally store the failure reason in metadata."""
        self.status = "failed"
        if reason:
            self.metadata.setdefault("failure", {})
            self.metadata["failure"]["reason"] = str(reason)
        self.save(update_fields=["status", "metadata", "updated_at"])

    def mark_expired(self):
        """Mark order as expired."""
        self.status = "expired"
        self.save(update_fields=["status", "updated_at"])

    # -------------------------
    # convenience creation helpers
    # -------------------------
    @classmethod
    def create_order(
        cls,
        user,
        purpose,
        amount,
        currency="INR",
        metadata=None,
        ttl_minutes=15,
        client_reference=None,
    ):
        """
        Factory helper to create a PaymentOrder with sensible defaults.
        - amount must be in paise (integer).
        - ttl_minutes sets expires_at = now + ttl_minutes.
        - returns the created PaymentOrder instance (still in status 'pending').
        """
        now = timezone.now()
        expires = now + timedelta(minutes=ttl_minutes)
        meta = metadata or {}

        # ensure the purpose is valid
        if purpose not in dict(PURPOSE_CHOICES):
            raise ValueError("Invalid purpose for PaymentOrder")

        obj = cls.objects.create(
            user=user,
            purpose=purpose,
            amount=amount,
            currency=currency,
            metadata=meta,
            expires_at=expires,
            client_reference=(client_reference or uuid.uuid4().hex),
            status="pending",
        )
        return obj

    # -------------------------
    # gateway helpers (placeholders)
    # -------------------------
    def prepare_gateway_payload(self):
        """
        Returns a dict ready to be sent to the payment gateway when creating an order.
        Keep this generic; actual Razorpay integration should live in services/ (not in model).
        """
        return {
            "amount": self.amount,
            "currency": self.currency,
            "receipt": self.client_reference,
            "notes": {
                "user_id": str(self.user_id),
                "purpose": self.purpose,
                **(self.metadata or {}),
            },
        }
