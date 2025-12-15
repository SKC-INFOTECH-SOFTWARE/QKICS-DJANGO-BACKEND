import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q

User = settings.AUTH_USER_MODEL  # assumes custom user or 'auth.User'


class ExpertSlot(models.Model):
    """
    Represents a single slot created by an Expert.
    Each slot is a concrete window (start/end). Capacity is 1 by business rule.
    """
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expert = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='expert_slots'
    )  # or 'experts.ExpertProfile' if you keep profile separate
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    requires_approval = models.BooleanField(default=True)
    is_recurring = models.BooleanField(default=False)
    # recurrence FK optional, created only if recurring enabled
    status = models.CharField(max_length=16, choices=(
        ('ACTIVE', 'Active'),
        ('DISABLED', 'Disabled'),
    ), default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['expert', 'start_datetime']),
            models.Index(fields=['start_datetime']),
        ]
        ordering = ['start_datetime']

    def __str__(self):
        return f"{self.expert} | {self.start_datetime.isoformat()} → {self.end_datetime.isoformat()}"


class SlotRecurringPattern(models.Model):
    """
    Optional lightweight recurring pattern for weekly slots.
    Create concrete ExpertSlot instances from this pattern in a background job.
    """
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    expert = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='slot_patterns')
    weekday = models.PositiveSmallIntegerField()  # 0=Monday .. 6=Sunday (or 0..6 as you prefer)
    start_time = models.TimeField()
    end_time = models.TimeField()
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['expert', 'weekday']),
        ]

    def __str__(self):
        return f"{self.expert} | weekday {self.weekday} {self.start_time}-{self.end_time}"


class Booking(models.Model):
    """
    Core booking record. Minimal fields kept for scale.
    Snapshots: price & fee fields are stored for audit and payouts.
    """
    STATUS_PENDING = 'PENDING'          # waiting for expert approval (if required)
    STATUS_AWAITING_PAYMENT = 'AWAITING_PAYMENT'  # approved, waiting user to pay
    STATUS_PAID = 'PAID'                # payment success
    STATUS_CONFIRMED = 'CONFIRMED'      # confirmed & chat unlocked
    STATUS_COMPLETED = 'COMPLETED'      # session completed
    STATUS_DECLINED = 'DECLINED'        # expert rejected before payment
    STATUS_FAILED = 'FAILED'            # payment or other failure

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pending'),
        (STATUS_AWAITING_PAYMENT, 'Awaiting Payment'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DECLINED, 'Declined'),
        (STATUS_FAILED, 'Failed'),
    )
    
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    expert = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='bookings_as_expert')
    slot = models.ForeignKey(ExpertSlot, on_delete=models.PROTECT, related_name='bookings')
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # snapshot fields (important for audit and later payout)
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    platform_fee_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('20.00'))
    platform_fee_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    expert_earning_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    requires_expert_approval = models.BooleanField(default=True)
    expert_approved_at = models.DateTimeField(null=True, blank=True)

    paid_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    chat_room_id = models.UUIDField(null=True, blank=True)  # populate when confirmed
    reschedule_count = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['expert', 'status']),
            models.Index(fields=['start_datetime']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(
                    status__in=[
                        'AWAITING_PAYMENT',
                        'PAID',
                        'CONFIRMED',
                    ]
                ),
                name="unique_active_booking_per_slot",
            )
        ]

        
    def __str__(self):
        return f"Booking {self.id} | {self.user} → {self.expert} @ {self.start_datetime.isoformat()}"

    def compute_fee_snapshot(self):
        """
        Helper to populate fee fields. Call inside a transaction when creating a booking or when price changes.
        """
        # platform_fee_percent is stored; compute amounts
        pct = (self.platform_fee_percent or Decimal('0.0')) / Decimal('100')
        self.platform_fee_amount = (self.price * pct).quantize(Decimal('0.01'))
        self.expert_earning_amount = (self.price - self.platform_fee_amount).quantize(Decimal('0.01'))


class BookingPayment(models.Model):
    """
    Lightweight payment record per booking. Keep minimal fields for scale.
    """
    GATEWAY_RAZORPAY = 'RAZORPAY'

    GATEWAY_CHOICES = (
        (GATEWAY_RAZORPAY, 'Razorpay'),
    )

    STATUS_CREATED = 'CREATED'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAILED = 'FAILED'

    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
    )

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    gateway = models.CharField(max_length=24, choices=GATEWAY_CHOICES, default=GATEWAY_RAZORPAY)
    order_id = models.CharField(max_length=128, null=True, blank=True)
    payment_id = models.CharField(max_length=128, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    payment_signature = models.CharField(max_length=512, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['booking', 'status']),
            models.Index(fields=['user', 'status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.id} | {self.booking_id} | {self.amount} | {self.status}"


class BookingReview(models.Model):
    """
    Rating/review for a completed booking.
    """
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='review')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booking_reviews')
    expert = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField()  # 1..5
    comment = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['expert', 'rating']),
        ]

    def __str__(self):
        return f"Review {self.rating} | {self.booking_id}"
