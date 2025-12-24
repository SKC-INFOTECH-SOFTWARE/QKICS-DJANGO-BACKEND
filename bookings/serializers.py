from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import ExpertSlot, Booking


# ============================================================
# EXPERT SLOT SERIALIZERS
# ============================================================


class ExpertSlotSerializer(serializers.ModelSerializer):
    """Read-only serializer for listing slots"""
    expert_name = serializers.CharField(source="expert.username", read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = ExpertSlot
        fields = [
            "id",
            "uuid",
            "expert",
            "expert_name",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "price",
            "requires_approval",
            "is_recurring",
            "status",
            "is_available",
            "created_at",
        ]
        read_only_fields = fields

    def get_is_available(self, obj):
        """Check if slot is available for booking"""
        return obj.is_available()


class ExpertSlotCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new slots"""
    
    class Meta:
        model = ExpertSlot
        fields = [
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "price",
            "requires_approval",
        ]

    def validate_start_datetime(self, value):
        """Ensure slot is not in the past"""
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Cannot create slots in the past."
            )
        return value

    def validate(self, attrs):
        """Validate time consistency and check for overlaps"""
        start = attrs.get("start_datetime")
        end = attrs.get("end_datetime")
        
        # Validate time order
        if end <= start:
            raise serializers.ValidationError({
                "end_datetime": "End time must be after start time."
            })
        
        # Check for overlapping slots
        expert = self.context["request"].user
        overlapping = ExpertSlot.objects.filter(
            expert=expert,
            status="ACTIVE",
            start_datetime__lt=end,
            end_datetime__gt=start,
        ).exists()
        
        if overlapping:
            raise serializers.ValidationError(
                "This slot overlaps with an existing slot."
            )
        
        return attrs

    def create(self, validated_data):
        """Create slot with expert from request"""
        expert = self.context["request"].user
        return ExpertSlot.objects.create(expert=expert, **validated_data)


class ExpertSlotUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating existing slots"""
    
    class Meta:
        model = ExpertSlot
        fields = [
            "start_datetime",
            "end_datetime",
            "price",
            "requires_approval",
            "status",
        ]

    def validate_start_datetime(self, value):
        """Prevent moving slot to the past"""
        if value <= timezone.now():
            raise serializers.ValidationError(
                "Cannot move slot to the past."
            )
        return value

    def validate(self, attrs):
        """Validate time consistency for partial updates"""
        instance = self.instance
        start = attrs.get("start_datetime", instance.start_datetime)
        end = attrs.get("end_datetime", instance.end_datetime)
        
        # Validate time order
        if end <= start:
            raise serializers.ValidationError({
                "end_datetime": "End time must be after start time."
            })
        
        return attrs

    def update(self, instance, validated_data):
        """
        Update slot with additional validations.
        CRITICAL: Check for active bookings and overlaps.
        """
        # CRITICAL FIX: Prevent updating slots with active bookings
        if instance.has_active_bookings():
            raise serializers.ValidationError(
                "Cannot modify slot with active bookings. "
                "Cancel or complete bookings first, or disable the slot."
            )
        
        # Check for overlaps with new times
        start = validated_data.get("start_datetime", instance.start_datetime)
        end = validated_data.get("end_datetime", instance.end_datetime)
        
        overlapping = ExpertSlot.objects.filter(
            expert=instance.expert,
            status="ACTIVE",
            start_datetime__lt=end,
            end_datetime__gt=start,
        ).exclude(id=instance.id).exists()
        
        if overlapping:
            raise serializers.ValidationError(
                "Updated times overlap with an existing slot."
            )

        return super().update(instance, validated_data)


# ============================================================
# BOOKING SERIALIZERS
# ============================================================


class BookingSerializer(serializers.ModelSerializer):
    """Read-only serializer for booking details"""
    user_name = serializers.CharField(source="user.username", read_only=True)
    expert_name = serializers.CharField(source="expert.username", read_only=True)
    slot_uuid = serializers.UUIDField(source="slot.uuid", read_only=True)
    can_be_cancelled = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "uuid",
            "user",
            "user_name",
            "expert",
            "expert_name",
            "slot",
            "slot_uuid",
            "status",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "price",
            "platform_fee_percent",
            "platform_fee_amount",
            "expert_earning_amount",
            "requires_expert_approval",
            "expert_approved_at",
            "paid_at",
            "confirmed_at",
            "completed_at",
            "declined_at",
            "cancelled_at",
            "chat_room_id",
            "reschedule_count",
            "cancellation_reason",
            "decline_reason",
            "created_at",
            "updated_at",
            "can_be_cancelled",
        ]
        read_only_fields = fields

    def get_can_be_cancelled(self, obj):
        """Check if booking can be cancelled"""
        return obj.can_be_cancelled()


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new bookings.
    CRITICAL: Entire operation wrapped in transaction for race condition prevention.
    """
    slot_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Booking
        fields = ["slot_id", "price"]
        extra_kwargs = {"price": {"required": False}}

    def validate_slot_id(self, value):
        """Basic slot existence check"""
        try:
            slot = ExpertSlot.objects.get(uuid=value)
            return value
        except ExpertSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not found.")

    @transaction.atomic
    def validate(self, attrs):
        """
        CRITICAL FIX: Run inside transaction so select_for_update works.
        This prevents race conditions on concurrent booking attempts.
        """
        user = self.context["request"].user
        slot_id = attrs.get("slot_id")

        # Lock the slot row to prevent concurrent bookings
        try:
            slot = ExpertSlot.objects.select_for_update().get(
                uuid=slot_id, status="ACTIVE"
            )
        except ExpertSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not available.")

        # Prevent self-booking
        if slot.expert == user:
            raise serializers.ValidationError("You cannot book your own slot.")

        # Prevent booking past slots
        if slot.start_datetime <= timezone.now():
            raise serializers.ValidationError("Cannot book past or ongoing slots.")

        # CRITICAL: Check for existing active bookings (includes PENDING!)
        # This check is now atomic due to select_for_update above
        existing_booking = Booking.objects.filter(
            slot=slot,
            status__in=Booking.ACTIVE_STATUSES,
        ).exists()

        if existing_booking:
            raise serializers.ValidationError("Slot already booked.")

        # Check if user already has a booking for this slot
        user_has_booking = Booking.objects.filter(
            user=user,
            slot=slot,
            status__in=Booking.ACTIVE_STATUSES,
        ).exists()

        if user_has_booking:
            raise serializers.ValidationError(
                "You already have an active booking for this slot."
            )

        attrs["slot"] = slot
        return attrs

    def create(self, validated_data):
        """
        Create booking with computed fees.
        Already inside transaction from validate().
        """
        user = self.context["request"].user
        slot = validated_data["slot"]
        price = validated_data.get("price", slot.price)

        # Determine initial status based on approval requirement
        if slot.requires_approval:
            initial_status = Booking.STATUS_PENDING
        else:
            initial_status = Booking.STATUS_AWAITING_PAYMENT

        # Create booking instance
        booking = Booking(
            user=user,
            expert=slot.expert,
            slot=slot,
            start_datetime=slot.start_datetime,
            end_datetime=slot.end_datetime,
            duration_minutes=slot.duration_minutes,
            price=price,
            requires_expert_approval=slot.requires_approval,
            status=initial_status,
        )
        
        # Compute platform fees
        booking.compute_fee_snapshot()
        booking.save()

        return booking


class BookingApprovalSerializer(serializers.Serializer):
    """Serializer for expert to approve/decline bookings"""
    approve = serializers.BooleanField()
    decline_reason = serializers.CharField(
        required=False, 
        allow_blank=True,
        max_length=500,
        help_text="Reason for declining (optional)"
    )

    def validate(self, attrs):
        """Validate booking can be approved/declined"""
        booking = self.context["booking"]
        approve = attrs.get("approve")
        
        # CRITICAL: Validate current status
        if booking.status != Booking.STATUS_PENDING:
            raise serializers.ValidationError(
                f"Cannot approve/decline booking in '{booking.status}' status. "
                f"Only PENDING bookings can be approved or declined."
            )
        
        # If approving, check slot hasn't been taken
        if approve:
            # Check if another booking has taken the slot
            conflicting_booking = Booking.objects.filter(
                slot=booking.slot,
                status__in=[
                    Booking.STATUS_AWAITING_PAYMENT,
                    Booking.STATUS_PAID,
                    Booking.STATUS_CONFIRMED,
                ],
            ).exclude(id=booking.id).exists()
            
            if conflicting_booking:
                raise serializers.ValidationError(
                    "Cannot approve: slot has already been booked by another user."
                )
        
        # If declining without approval, reason is helpful but not required
        if not approve and not attrs.get("decline_reason"):
            attrs["decline_reason"] = "Declined by expert"
        
        return attrs


class BookingCancellationSerializer(serializers.Serializer):
    """Serializer for cancelling bookings"""
    cancellation_reason = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Reason for cancellation (optional)"
    )

    def validate(self, attrs):
        """Validate booking can be cancelled"""
        booking = self.context["booking"]
        
        if not booking.can_be_cancelled():
            raise serializers.ValidationError(
                f"Cannot cancel booking in '{booking.status}' status."
            )
        
        # Set default reason if not provided
        if not attrs.get("cancellation_reason"):
            attrs["cancellation_reason"] = "Cancelled by user"
        
        return attrs


class BookingStatusUpdateSerializer(serializers.Serializer):
    """
    Generic serializer for status updates (for admin/system use).
    Validates state transitions.
    """
    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        """Validate status transition is allowed"""
        booking = self.context["booking"]
        new_status = attrs.get("status")
        
        if not booking.can_transition_to(new_status):
            raise serializers.ValidationError(
                f"Cannot transition from '{booking.status}' to '{new_status}'. "
                f"Invalid state transition."
            )
        
        return attrs