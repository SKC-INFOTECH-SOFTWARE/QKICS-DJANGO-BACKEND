import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


class ExpertSlot(models.Model):
    """
    Represents a single slot created by an Expert.
    Each slot is a concrete window (start/end). Capacity is 1 by business rule.
    """

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expert = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="expert_slots"
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    requires_approval = models.BooleanField(default=True)
    is_recurring = models.BooleanField(default=False)
    status = models.CharField(
        max_length=16,
        choices=(
            ("ACTIVE", "Active"),
            ("DISABLED", "Disabled"),
        ),
        default="ACTIVE",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Added for tracking changes

    class Meta:
        indexes = [
            models.Index(fields=["expert", "start_datetime"]),
            models.Index(fields=["start_datetime"]),
            models.Index(fields=["expert", "status"]),
            models.Index(fields=["uuid"]),  # For faster UUID lookups
        ]
        ordering = ["start_datetime"]
        # FIX: Add constraint to prevent overlapping slots for same expert
        constraints = [
            models.CheckConstraint(
                check=Q(end_datetime__gt=models.F("start_datetime")),
                name="slot_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.expert} | {self.start_datetime.isoformat()} → {self.end_datetime.isoformat()}"

    def clean(self):
        """Model-level validation"""
        super().clean()

        if self.end_datetime <= self.start_datetime:
            raise ValidationError("End datetime must be after start datetime.")

        if self.start_datetime < timezone.now():
            raise ValidationError("Cannot create slots in the past.")

    def is_available(self):
        """
        Check if slot is available for booking.
        Returns True if slot is active, in the future, and has no active bookings.
        """
        if self.status != "ACTIVE":
            return False

        if self.start_datetime <= timezone.now():
            return False

        # Check if there's any active booking
        return not self.bookings.filter(
            status__in=[
                Booking.STATUS_PENDING,
                Booking.STATUS_AWAITING_PAYMENT,
                Booking.STATUS_PAID,
                Booking.STATUS_CONFIRMED,
            ]
        ).exists()

    def has_active_bookings(self):
        """Check if slot has any active bookings"""
        return self.bookings.filter(
            status__in=[
                Booking.STATUS_PENDING,
                Booking.STATUS_AWAITING_PAYMENT,
                Booking.STATUS_PAID,
                Booking.STATUS_CONFIRMED,
            ]
        ).exists()


class SlotRecurringPattern(models.Model):
    """
    Optional lightweight recurring pattern for weekly slots.
    Create concrete ExpertSlot instances from this pattern in a background job.
    """

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expert = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="slot_patterns"
    )
    weekday = models.PositiveSmallIntegerField()  # 0=Monday .. 6=Sunday
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # Added to enable/disable patterns
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["expert", "weekday"]),
            models.Index(fields=["expert", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(weekday__gte=0) & Q(weekday__lte=6),
                name="valid_weekday",
            ),
            models.CheckConstraint(
                check=Q(end_time__gt=models.F("start_time")),
                name="pattern_end_after_start",
            ),
        ]

    def __str__(self):
        return (
            f"{self.expert} | weekday {self.weekday} {self.start_time}-{self.end_time}"
        )

    def clean(self):
        """Model-level validation"""
        super().clean()

        if self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")

        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date must be after start date.")


class Booking(models.Model):
    """
    Core booking record. Minimal fields kept for scale.
    Snapshots: price & fee fields are stored for audit and payouts.
    """

    # Status definitions
    STATUS_PENDING = "PENDING"  # Waiting for expert approval (if required)
    STATUS_AWAITING_PAYMENT = "AWAITING_PAYMENT"  # Approved, waiting for payment
    STATUS_PAID = "PAID"  # Payment successful
    STATUS_CONFIRMED = "CONFIRMED"  # Confirmed & chat unlocked
    STATUS_COMPLETED = "COMPLETED"  # Session completed
    STATUS_DECLINED = "DECLINED"  # Expert rejected before payment
    STATUS_CANCELLED = "CANCELLED"  # User cancelled
    STATUS_FAILED = "FAILED"  # Payment or other failure
    STATUS_EXPIRED = "EXPIRED"  # Booking expired without action

    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_AWAITING_PAYMENT, "Awaiting Payment"),
        (STATUS_PAID, "Paid"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_DECLINED, "Declined"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_FAILED, "Failed"),
        (STATUS_EXPIRED, "Expired"),
    )

    # Active statuses that block the slot
    ACTIVE_STATUSES = [
        STATUS_PENDING,
        STATUS_AWAITING_PAYMENT,
        STATUS_PAID,
        STATUS_CONFIRMED,
    ]

    # Terminal statuses that don't block the slot
    TERMINAL_STATUSES = [
        STATUS_COMPLETED,
        STATUS_DECLINED,
        STATUS_CANCELLED,
        STATUS_FAILED,
        STATUS_EXPIRED,
    ]

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    expert = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="bookings_as_expert"
    )
    slot = models.ForeignKey(
        ExpertSlot, on_delete=models.PROTECT, related_name="bookings"
    )
    status = models.CharField(
        max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    # Snapshot fields (important for audit and later payout)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("20.00")
    )
    platform_fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    expert_earning_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )

    requires_expert_approval = models.BooleanField(default=True)
    expert_approved_at = models.DateTimeField(null=True, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)  # Added
    cancelled_at = models.DateTimeField(null=True, blank=True)  # Added
    expired_at = models.DateTimeField(null=True, blank=True)  # Added

    chat_room_id = models.UUIDField(null=True, blank=True)
    reschedule_count = models.PositiveSmallIntegerField(default=0)

    # Added for better tracking
    payment_intent_id = models.CharField(
        max_length=255, null=True, blank=True
    )  # For Stripe/payment gateway
    cancellation_reason = models.TextField(null=True, blank=True)
    decline_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["expert", "status"]),
            models.Index(fields=["start_datetime"]),
            models.Index(fields=["uuid"]),
            models.Index(fields=["status", "created_at"]),  # For cleanup queries
            models.Index(fields=["slot", "status"]),  # For slot availability checks
        ]
        constraints = [
            # CRITICAL FIX: Include PENDING to prevent double bookings
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(
                    status__in=[
                        "PENDING",
                        "AWAITING_PAYMENT",
                        "PAID",
                        "CONFIRMED",
                    ]
                ),
                name="unique_active_booking_per_slot",
            ),
            # Prevent user from booking multiple times on same slot
            models.UniqueConstraint(
                fields=["user", "slot"],
                condition=Q(
                    status__in=[
                        "PENDING",
                        "AWAITING_PAYMENT",
                        "PAID",
                        "CONFIRMED",
                        "COMPLETED",
                    ]
                ),
                name="unique_user_booking_per_slot",
            ),
        ]

    def __str__(self):
        return f"Booking {self.id} | {self.user} → {self.expert} @ {self.start_datetime.isoformat()}"

    def clean(self):
        """Model-level validation"""
        super().clean()

        if hasattr(self, "user") and hasattr(self, "expert"):
            if self.user == self.expert:
                raise ValidationError("User cannot book their own slot.")

    def compute_fee_snapshot(self):
        """
        Helper to populate fee fields. Call before saving when creating/updating price.
        """
        pct = (self.platform_fee_percent or Decimal("0.0")) / Decimal("100")
        self.platform_fee_amount = (self.price * pct).quantize(Decimal("0.01"))
        self.expert_earning_amount = (self.price - self.platform_fee_amount).quantize(
            Decimal("0.01")
        )

    def is_active(self):
        """Check if booking is in an active state"""
        return self.status in self.ACTIVE_STATUSES

    def is_terminal(self):
        """Check if booking is in a terminal state"""
        return self.status in self.TERMINAL_STATUSES

    def can_be_cancelled(self):
        """Check if booking can be cancelled by user"""
        return self.status in [
            self.STATUS_PENDING,
            self.STATUS_AWAITING_PAYMENT,
            self.STATUS_PAID,
            self.STATUS_CONFIRMED,
        ]

    def can_transition_to(self, new_status):
        """
        Validate if transition to new_status is allowed.
        Prevents invalid state transitions.
        """
        # Define valid state transitions
        valid_transitions = {
            self.STATUS_PENDING: [
                self.STATUS_AWAITING_PAYMENT,
                self.STATUS_DECLINED,
                self.STATUS_CANCELLED,
                self.STATUS_EXPIRED,
                self.STATUS_FAILED,
            ],
            self.STATUS_AWAITING_PAYMENT: [
                self.STATUS_PAID,
                self.STATUS_CANCELLED,
                self.STATUS_EXPIRED,
                self.STATUS_FAILED,
            ],
            self.STATUS_PAID: [
                self.STATUS_CONFIRMED,
                self.STATUS_CANCELLED,
                self.STATUS_FAILED,
            ],
            self.STATUS_CONFIRMED: [
                self.STATUS_COMPLETED,
                self.STATUS_CANCELLED,
            ],
            self.STATUS_COMPLETED: [],  # Terminal state
            self.STATUS_DECLINED: [],  # Terminal state
            self.STATUS_CANCELLED: [],  # Terminal state
            self.STATUS_FAILED: [],  # Terminal state
            self.STATUS_EXPIRED: [],  # Terminal state
        }

        return new_status in valid_transitions.get(self.status, [])

    def mark_as_expired(self):
        """Mark booking as expired"""
        if self.can_transition_to(self.STATUS_EXPIRED):
            self.status = self.STATUS_EXPIRED
            self.expired_at = timezone.now()
            self.save(update_fields=["status", "expired_at", "updated_at"])
            return True
        return False

    def mark_as_completed(self):
        """Mark booking as completed"""
        if self.can_transition_to(self.STATUS_COMPLETED):
            self.status = self.STATUS_COMPLETED
            self.completed_at = timezone.now()
            self.save(update_fields=["status", "completed_at", "updated_at"])
            return True
        return False
