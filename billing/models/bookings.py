# billing/models/bookings.py

from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta, datetime
import uuid

from .orders import PaymentOrder
from experts.models import ExpertProfile


# ---------------------------------------------------------
# EXPERT SLOT MODEL — Weekly Recurring Schedule
# ---------------------------------------------------------
class ExpertSlot(models.Model):
    """
    Weekly recurring slot created by the expert.
    Example:
        Monday 10:00–12:00 every week.
    """

    expert = models.ForeignKey(
        ExpertProfile, on_delete=models.CASCADE, related_name="slots"
    )

    weekday = models.PositiveSmallIntegerField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ]
    )

    start_time = models.TimeField()
    end_time = models.TimeField()

    is_active = models.BooleanField(default=True)
    soft_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def duration_minutes(self):
        dt_start = datetime.combine(timezone.now().date(), self.start_time)
        dt_end = datetime.combine(timezone.now().date(), self.end_time)
        return int((dt_end - dt_start).total_seconds() / 60)

    def __str__(self):
        return f"{self.expert.user.username} — {self.get_weekday_display()} {self.start_time}-{self.end_time}"

    class Meta:
        ordering = ["weekday", "start_time"]
        indexes = [
            models.Index(fields=["expert", "weekday"]),
            models.Index(fields=["is_active"]),
        ]


# ---------------------------------------------------------
# BOOKING MODEL — Final, Race-Condition-Safe Version
# ---------------------------------------------------------
BOOKING_STATUS = [
    ("pending_approval", "Pending Expert Approval"),
    ("awaiting_payment", "Awaiting Payment"),
    ("confirmed", "Confirmed"),
    ("active", "Active Chat"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
    ("expired", "Expired"),
]


class ExpertBooking(models.Model):
    """
    The definitive booking model handling:
    - approval → payment → confirmation
    - recurring slots
    - rescheduling
    - full race-condition protection
    - chat room integration
    """

    # User who books
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expert_bookings",
    )

    # The expert being booked
    expert = models.ForeignKey(
        ExpertProfile, on_delete=models.CASCADE, related_name="expert_sessions"
    )

    # Slot used
    slot = models.ForeignKey(
        ExpertSlot, on_delete=models.PROTECT, related_name="bookings"
    )

    scheduled_for = models.DateTimeField(db_index=True)
    duration_minutes = models.PositiveIntegerField()

    # Payment Order link
    order = models.OneToOneField(
        PaymentOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking",
    )

    status = models.CharField(
        max_length=20, choices=BOOKING_STATUS, default="pending_approval"
    )

    # Pricing snapshot
    expert_fee = models.PositiveIntegerField(default=0)
    platform_fee = models.PositiveIntegerField(default=0)
    is_free = models.BooleanField(default=False)

    # Chat
    room_id = models.CharField(max_length=120, unique=True, null=True, blank=True)
    chat_started_at = models.DateTimeField(null=True, blank=True)
    chat_ended_at = models.DateTimeField(null=True, blank=True)

    # Rescheduling
    reschedule_count = models.PositiveIntegerField(default=0)
    max_reschedules = models.PositiveIntegerField(default=2)
    rescheduled_from = models.DateTimeField(null=True, blank=True)

    # Cancellation reason or server-expiry explanation
    cancellation_reason = models.TextField(null=True, blank=True)
    frozen_by_server = models.BooleanField(default=False)  # prevents further changes

    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # ---------------------------------------------------------
    # UTILITY FUNCTIONS
    # ---------------------------------------------------------
    def generate_room_id_atomic(self):
        """Atomic room_id generator."""
        if not self.room_id:
            self.room_id = f"chat_{uuid.uuid4().hex}"
            self.save(update_fields=["room_id"])

    # ---------------------------------------------------------
    # SLOT WINDOW CALCULATION — FIXED
    # ---------------------------------------------------------
    def slot_window(self):
        """
        Map scheduled_for to the SAME DATE's slot start/end.
        Ensures timezone correctness and weekday match.
        """
        if not self.scheduled_for:
            raise ValidationError("scheduled_for must be set")

        tz = timezone.get_current_timezone()
        scheduled = self.scheduled_for

        if not timezone.is_aware(scheduled):
            scheduled = timezone.make_aware(scheduled, tz)

        # Ensure weekday matches slot
        if scheduled.weekday() != self.slot.weekday:
            raise ValidationError("scheduled_for weekday must match slot.weekday")

        date = scheduled.date()
        start_naive = datetime.combine(date, self.slot.start_time)
        end_naive = datetime.combine(date, self.slot.end_time)

        start = timezone.make_aware(start_naive, tz)
        end = timezone.make_aware(end_naive, tz)

        return start, end

    # ---------------------------------------------------------
    # CLEAN — Lightweight Only
    # ---------------------------------------------------------
    def clean(self):
        if self.frozen_by_server:
            raise ValidationError("This booking is frozen and cannot be edited.")

        # Must be future
        tz = timezone.get_current_timezone()
        scheduled = self.scheduled_for

        if not timezone.is_aware(scheduled):
            scheduled = timezone.make_aware(scheduled, tz)

        if scheduled <= timezone.now():
            raise ValidationError("Cannot schedule booking in the past")

        # Slot active?
        if not self.slot.is_active or self.slot.soft_deleted:
            raise ValidationError("Slot is inactive or removed")

        # Slot window
        slot_start, slot_end = self.slot_window()
        last_start_allowed = slot_end - timedelta(minutes=self.duration_minutes)

        if not (slot_start <= scheduled <= last_start_allowed):
            raise ValidationError("Start time does not fit inside slot window")

        # Duration fits
        slot_len = int((slot_end - slot_start).total_seconds() / 60)
        if self.duration_minutes > slot_len:
            raise ValidationError("Duration exceeds slot window")

        # Limit active bookings per user
        MAX_ACTIVE = 5
        active_count = (
            ExpertBooking.objects.filter(
                user=self.user,
                status__in=[
                    "pending_approval",
                    "awaiting_payment",
                    "confirmed",
                    "active",
                ],
            )
            .exclude(pk=self.pk)
            .count()
        )

        if active_count >= MAX_ACTIVE:
            raise ValidationError(
                f"You cannot hold more than {MAX_ACTIVE} active bookings"
            )

    # ---------------------------------------------------------
    # CREATE BOOKING (ATOMIC, RACE-SAFE)
    # ---------------------------------------------------------
    @classmethod
    def create_booking_atomic(
        cls,
        user,
        slot,
        scheduled_for,
        duration_minutes,
        expert_fee=0,
        platform_fee=0,
        is_free=False,
        max_reschedules=2,
    ):
        tz = timezone.get_current_timezone()
        if not timezone.is_aware(scheduled_for):
            scheduled_for = timezone.make_aware(scheduled_for, tz)

        # Quick user same-day check (fast)
        if cls.objects.filter(
            user=user, expert=slot.expert, scheduled_for__date=scheduled_for.date()
        ).exists():
            raise ValidationError("You already have a booking with this expert today.")

        # Pre-validate outside transaction
        temp = cls(
            user=user,
            expert=slot.expert,
            slot=slot,
            scheduled_for=scheduled_for,
            duration_minutes=duration_minutes,
            expert_fee=expert_fee,
            platform_fee=platform_fee,
            is_free=is_free,
            max_reschedules=max_reschedules,
        )
        temp.full_clean()

        # Compute slot window + length
        slot_start, slot_end = temp.slot_window()
        slot_len = int((slot_end - slot_start).total_seconds() / 60)

        new_start = scheduled_for
        new_end = scheduled_for + timedelta(minutes=duration_minutes)

        candidate_start = new_start - timedelta(minutes=slot_len)
        candidate_end = new_end

        with transaction.atomic():
            # Lock slot
            locked_slot = (
                ExpertSlot.objects.select_for_update().filter(pk=slot.pk).first()
            )
            if not locked_slot or not locked_slot.is_active or locked_slot.soft_deleted:
                raise ValidationError("Slot unavailable")

            # Lock potentially conflicting bookings
            candidates = (
                cls.objects.select_for_update()
                .filter(
                    expert=slot.expert,
                    scheduled_for__lt=candidate_end,
                    scheduled_for__gte=candidate_start,
                )
                .exclude(status__in=["cancelled", "expired"])
            )

            # Check overlap manually
            for b in candidates:
                exists_start = b.scheduled_for
                exists_end = b.scheduled_for + timedelta(minutes=b.duration_minutes)
                if exists_start < new_end and exists_end > new_start:
                    raise ValidationError("Slot already booked")

            # Prevent race-same-day conflict
            if cls.objects.filter(
                user=user, expert=slot.expert, scheduled_for__date=scheduled_for.date()
            ).exists():
                raise ValidationError(
                    "Race: You already booked this expert for the same day."
                )

            # Create final booking
            booking = cls.objects.create(
                user=user,
                expert=slot.expert,
                slot=slot,
                scheduled_for=scheduled_for,
                duration_minutes=duration_minutes,
                expert_fee=expert_fee,
                platform_fee=platform_fee,
                is_free=is_free,
                max_reschedules=max_reschedules,
                status="confirmed",
            )

            booking.generate_room_id_atomic()
            return booking

    # ---------------------------------------------------------
    # STATUS HELPERS
    # ---------------------------------------------------------
    def mark_approved(self):
        self.status = "awaiting_payment"
        self.save(update_fields=["status"])

    def mark_confirmed(self):
        self.status = "confirmed"
        self.save(update_fields=["status"])

    def mark_active(self):
        self.status = "active"
        self.chat_started_at = timezone.now()
        self.save(update_fields=["status", "chat_started_at"])

    def mark_completed(self):
        self.status = "completed"
        self.chat_ended_at = timezone.now()
        self.save(update_fields=["status", "chat_ended_at"])

    def can_reschedule(self):
        return timezone.now() <= (self.scheduled_for - timedelta(hours=6))

    def reschedule_atomic(self, new_datetime):
        """Race-safe reschedule method can be added later."""
        raise NotImplementedError("reschedule_atomic() will be implemented next.")

    def __str__(self):
        return f"{self.user.username} → {self.expert.user.username} at {self.scheduled_for}"

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["expert", "scheduled_for"]),
            models.Index(fields=["user", "status"]),
        ]
        constraints = [
            # Prevent same payment order from being attached to multiple bookings
            models.UniqueConstraint(
                fields=["order"], name="unique_paymentorder_per_booking"
            ),
        ]
