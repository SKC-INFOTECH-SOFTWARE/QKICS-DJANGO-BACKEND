from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import ExpertSlot, Booking, InvestorSlot, InvestorBooking
from subscriptions.services.access import is_user_premium

class ExpertSlotSerializer(serializers.ModelSerializer):
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
        return obj.is_available()


class ExpertSlotCreateSerializer(serializers.ModelSerializer):
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
        if value <= timezone.now():
            raise serializers.ValidationError("Cannot create slots in the past.")
        return value

    def validate(self, attrs):
        start, end = attrs.get("start_datetime"), attrs.get("end_datetime")
        if end <= start:
            raise serializers.ValidationError(
                {"end_datetime": "End time must be after start time."}
            )
        expert = self.context["request"].user
        if ExpertSlot.objects.filter(
            expert=expert,
            status="ACTIVE",
            start_datetime__lt=end,
            end_datetime__gt=start,
        ).exists():
            raise serializers.ValidationError(
                "This slot overlaps with an existing slot."
            )
        return attrs


class ExpertSlotUpdateSerializer(serializers.ModelSerializer):
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
        if value <= timezone.now():
            raise serializers.ValidationError("Cannot move slot to the past.")
        return value

    def validate(self, attrs):
        instance = self.instance
        start = attrs.get("start_datetime", instance.start_datetime)
        end = attrs.get("end_datetime", instance.end_datetime)
        if end <= start:
            raise serializers.ValidationError(
                {"end_datetime": "End time must be after start time."}
            )
        return attrs

    def update(self, instance, validated_data):
        if instance.has_active_bookings():
            raise serializers.ValidationError(
                "Cannot modify slot with active bookings."
            )
        start = validated_data.get("start_datetime", instance.start_datetime)
        end = validated_data.get("end_datetime", instance.end_datetime)
        if (
            ExpertSlot.objects.filter(
                expert=instance.expert,
                status="ACTIVE",
                start_datetime__lt=end,
                end_datetime__gt=start,
            )
            .exclude(id=instance.id)
            .exists()
        ):
            raise serializers.ValidationError(
                "Updated times overlap with an existing slot."
            )
        return super().update(instance, validated_data)


class BookingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    expert_name = serializers.CharField(source="expert.username", read_only=True)
    slot_uuid = serializers.UUIDField(source="slot.uuid", read_only=True)
    can_be_cancelled = serializers.SerializerMethodField()
    call_room_id = serializers.SerializerMethodField()  # ← NEW

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
            "call_room_id",
        ]
        read_only_fields = fields

    def get_can_be_cancelled(self, obj):
        return obj.can_be_cancelled()

    def get_call_room_id(self, obj):
        try:
            return str(obj.call_room.id)
        except Exception:
            return None


class BookingCreateSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Booking
        fields = ["slot_id", "price"]
        extra_kwargs = {"price": {"required": False}}

    def validate_slot_id(self, value):
        try:
            ExpertSlot.objects.get(uuid=value)
            return value
        except ExpertSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not found.")

    @transaction.atomic
    def validate(self, attrs):
        user = self.context["request"].user
        slot_id = attrs.get("slot_id")
        try:
            slot = ExpertSlot.objects.select_for_update().get(
                uuid=slot_id, status="ACTIVE"
            )
        except ExpertSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not available.")
        if slot.expert == user:
            raise serializers.ValidationError("You cannot book your own slot.")
        if slot.start_datetime <= timezone.now():
            raise serializers.ValidationError("Cannot book past or ongoing slots.")
        if Booking.objects.filter(
            slot=slot, status__in=Booking.ACTIVE_STATUSES
        ).exists():
            raise serializers.ValidationError("Slot already booked.")
        if Booking.objects.filter(
            user=user, slot=slot, status__in=Booking.ACTIVE_STATUSES
        ).exists():
            raise serializers.ValidationError(
                "You already have a booking for this slot."
            )
        attrs["slot"] = slot
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        slot = validated_data["slot"]
        price = validated_data.get("price", slot.price)
        status = (
            Booking.STATUS_PENDING
            if slot.requires_approval
            else Booking.STATUS_AWAITING_PAYMENT
        )
        booking = Booking(
            user=user,
            expert=slot.expert,
            slot=slot,
            start_datetime=slot.start_datetime,
            end_datetime=slot.end_datetime,
            duration_minutes=slot.duration_minutes,
            price=price,
            requires_expert_approval=slot.requires_approval,
            status=status,
        )
        booking.compute_fee_snapshot()
        booking.save()
        return booking


class BookingApprovalSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    decline_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )

    def validate(self, attrs):
        booking = self.context["booking"]
        if booking.status != Booking.STATUS_PENDING:
            raise serializers.ValidationError(
                f"Cannot approve/decline booking in '{booking.status}' status."
            )
        if attrs.get("approve"):
            conflict = (
                Booking.objects.filter(
                    slot=booking.slot,
                    status__in=[
                        Booking.STATUS_AWAITING_PAYMENT,
                        Booking.STATUS_PAID,
                        Booking.STATUS_CONFIRMED,
                    ],
                )
                .exclude(id=booking.id)
                .exists()
            )
            if conflict:
                raise serializers.ValidationError(
                    "Slot already booked by another user."
                )
        if not attrs.get("approve") and not attrs.get("decline_reason"):
            attrs["decline_reason"] = "Declined by expert"
        return attrs


class BookingCancellationSerializer(serializers.Serializer):
    cancellation_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=500
    )

    def validate(self, attrs):
        booking = self.context["booking"]
        if not booking.can_be_cancelled():
            raise serializers.ValidationError(
                f"Cannot cancel booking in '{booking.status}' status."
            )
        if not attrs.get("cancellation_reason"):
            attrs["cancellation_reason"] = "Cancelled by user"
        return attrs


class BookingStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Booking.STATUS_CHOICES)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        booking = self.context["booking"]
        new_status = attrs.get("status")
        if not booking.can_transition_to(new_status):
            raise serializers.ValidationError(
                f"Cannot transition from '{booking.status}' to '{new_status}'."
            )
        return attrs


class InvestorSlotSerializer(serializers.ModelSerializer):
    investor_name = serializers.CharField(source="investor.username", read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = InvestorSlot
        fields = [
            "id",
            "uuid",
            "investor",
            "investor_name",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "status",
            "is_available",
            "created_at",
        ]
        read_only_fields = fields

    def get_is_available(self, obj):
        return obj.is_available()


class InvestorSlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestorSlot
        fields = ["start_datetime", "end_datetime", "duration_minutes"]

    def validate(self, attrs):
        start, end = attrs["start_datetime"], attrs["end_datetime"]
        if end <= start:
            raise serializers.ValidationError("End time must be after start time.")
        if start <= timezone.now():
            raise serializers.ValidationError("Cannot create slot in the past.")
        return attrs


class InvestorBookingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    investor_name = serializers.CharField(source="investor.username", read_only=True)
    call_room_id = serializers.SerializerMethodField()  # ← NEW

    class Meta:
        model = InvestorBooking
        fields = [
            "id",
            "uuid",
            "user",
            "user_name",
            "investor",
            "investor_name",
            "slot",
            "status",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "reschedule_count",
            "chat_room_id",
            "created_at",
            "call_room_id",
        ]
        read_only_fields = fields

    def get_call_room_id(self, obj):
        try:
            return str(obj.call_room.id)
        except Exception:
            return None


class InvestorBookingCreateSerializer(serializers.Serializer):
    slot_id = serializers.UUIDField()

    @transaction.atomic
    def validate(self, attrs):
        user = self.context["request"].user
        if not is_user_premium(user):
            raise serializers.ValidationError(
                "Investor consultations are available only for premium users."
            )
        try:
            slot = InvestorSlot.objects.select_for_update().get(
                uuid=attrs["slot_id"], status="ACTIVE"
            )
        except InvestorSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not available.")
        if slot.investor == user:
            raise serializers.ValidationError("You cannot book your own slot.")
        if not slot.is_available():
            raise serializers.ValidationError("Slot already booked.")
        attrs["slot"] = slot
        return attrs
