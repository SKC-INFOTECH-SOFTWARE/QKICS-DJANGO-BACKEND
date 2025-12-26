import uuid
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Payment(models.Model):
    """
    Generic payment record.
    Used for bookings, subscriptions, and documents.
    """

    # --------------------------------------------------
    # ENUMS
    # --------------------------------------------------

    PURPOSE_BOOKING = "BOOKING"
    PURPOSE_SUBSCRIPTION = "SUBSCRIPTION"
    PURPOSE_DOCUMENT = "DOCUMENT"

    PURPOSE_CHOICES = (
        (PURPOSE_BOOKING, "Booking"),
        (PURPOSE_SUBSCRIPTION, "Subscription"),
        (PURPOSE_DOCUMENT, "Document"),
    )

    STATUS_INITIATED = "INITIATED"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = (
        (STATUS_INITIATED, "Initiated"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    )

    GATEWAY_FAKE = "FAKE"
    GATEWAY_RAZORPAY = "RAZORPAY"

    GATEWAY_CHOICES = (
        (GATEWAY_FAKE, "Fake"),
        (GATEWAY_RAZORPAY, "Razorpay"),
    )

    # --------------------------------------------------
    # CORE FIELDS
    # --------------------------------------------------

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    purpose = models.CharField(
        max_length=20,
        choices=PURPOSE_CHOICES,
    )

    # booking_id / subscription_id / document_id
    reference_id = models.UUIDField()

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_INITIATED,
    )

    gateway = models.CharField(
        max_length=20,
        choices=GATEWAY_CHOICES,
        default=GATEWAY_FAKE,
    )

    # --------------------------------------------------
    # GATEWAY DATA (SAFE FOR FUTURE)
    # --------------------------------------------------

    gateway_order_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Order ID from payment gateway",
    )

    gateway_payment_id = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Payment ID from payment gateway",
    )

    gateway_response = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw gateway response for debugging/audit",
    )

    # --------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --------------------------------------------------
    # META
    # --------------------------------------------------

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["purpose", "reference_id"]),
            models.Index(fields=["gateway"]),
        ]

    def __str__(self):
        return (
            f"Payment {self.uuid} | {self.user} | "
            f"{self.purpose} | {self.amount} | {self.status}"
        )
