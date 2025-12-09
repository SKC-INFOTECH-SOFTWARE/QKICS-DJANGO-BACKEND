from rest_framework import serializers
from .models import ExpertSlot, Booking, BookingPayment, BookingReview
from django.utils import timezone


# -------------------------------
# Expert Slot Serializer
# -------------------------------
class ExpertSlotSerializer(serializers.ModelSerializer):
    expert_name = serializers.CharField(source="expert.username", read_only=True)

    class Meta:
        model = ExpertSlot
        fields = [
            "id",
            "expert",
            "expert_name",
            "start_datetime",
            "end_datetime",
            "duration_minutes",
            "price",
            "requires_approval",
            "is_recurring",
            "status",
        ]
        read_only_fields = ["expert", "status"]


# -------------------------------
# Booking Create Serializer
# -------------------------------
class BookingCreateSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = Booking
        fields = [
            "slot_id",
            "price",  # optional override if needed
        ]
        extra_kwargs = {
            "price": {"required": False},
        }

    def validate(self, attrs):
        user = self.context["request"].user
        slot_id = attrs.get("slot_id")

        try:
            slot = ExpertSlot.objects.get(id=slot_id, status="ACTIVE")
        except ExpertSlot.DoesNotExist:
            raise serializers.ValidationError("Slot not available.")

        if slot.start_datetime <= timezone.now():
            raise serializers.ValidationError("Cannot book past or ongoing slots.")

        # Prevent double booking
        if Booking.objects.filter(
            slot=slot,
            status__in=[
                Booking.STATUS_CONFIRMED,
                Booking.STATUS_PAID,
                Booking.STATUS_AWAITING_PAYMENT,
            ],
        ).exists():
            raise serializers.ValidationError("Slot already booked by another user.")

        attrs["slot"] = slot
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        slot = validated_data["slot"]

        # price snapshot
        price = validated_data.get("price", slot.price)

        booking = Booking.objects.create(
            user=user,
            expert=slot.expert,
            slot=slot,
            start_datetime=slot.start_datetime,
            end_datetime=slot.end_datetime,
            duration_minutes=slot.duration_minutes,
            price=price,
            requires_expert_approval=slot.requires_approval,
        )

        # compute platform + expert fee
        booking.compute_fee_snapshot()
        booking.save()

        return booking


# -------------------------------
# Booking Detail Serializer
# -------------------------------
class BookingSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    expert_name = serializers.CharField(source="expert.username", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "user",
            "user_name",
            "expert",
            "expert_name",
            "slot",
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
            "chat_room_id",
            "reschedule_count",
            "created_at",
        ]
        read_only_fields = fields


# -------------------------------
# Expert Booking Approval Serializer
# -------------------------------
class BookingApprovalSerializer(serializers.Serializer):
    approve = serializers.BooleanField()

    def validate(self, attrs):
        booking = self.context["booking"]

        if booking.status != Booking.STATUS_PENDING:
            raise serializers.ValidationError("Booking is not waiting for approval.")

        return attrs


# -------------------------------
# Payment Create Serializer (Razorpay Order)
# -------------------------------
class BookingPaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingPayment
        fields = ["id", "booking", "amount", "gateway", "status"]
        read_only_fields = ["id", "status", "gateway", "booking"]


# -------------------------------
# Payment Update Serializer (Webhook or Client Confirm)
# -------------------------------
class BookingPaymentUpdateSerializer(serializers.Serializer):
    order_id = serializers.CharField()
    payment_id = serializers.CharField()
    payment_signature = serializers.CharField()

    def validate(self, attrs):
        # Razorpay signature verification done in view
        return attrs


# -------------------------------
# Booking Review Serializer
# -------------------------------
class BookingReviewSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    expert_name = serializers.CharField(source="expert.username", read_only=True)

    class Meta:
        model = BookingReview
        fields = [
            "id",
            "booking",
            "user",
            "expert",
            "user_name",
            "expert_name",
            "rating",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "user", "expert", "created_at"]

    def validate(self, attrs):
        booking = self.context["booking"]
        user = self.context["request"].user

        if booking.status != Booking.STATUS_COMPLETED:
            raise serializers.ValidationError("Cannot review an incomplete session.")

        if booking.user != user:
            raise serializers.ValidationError("You can only review your own booking.")

        if hasattr(booking, "review"):
            raise serializers.ValidationError("Review already exists for this booking.")

        return attrs

    def create(self, validated_data):
        booking = self.context["booking"]
        user = self.context["request"].user

        validated_data["booking"] = booking
        validated_data["user"] = user
        validated_data["expert"] = booking.expert

        return super().create(validated_data)


# -------------------------------
# Slot Create Serializer
# -------------------------------
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

    def validate(self, attrs):
        if attrs["end_datetime"] <= attrs["start_datetime"]:
            raise serializers.ValidationError("End time must be after start time.")
        return attrs

    def create(self, validated_data):
        expert = self.context["request"].user
        return ExpertSlot.objects.create(
            **validated_data
        )


# -------------------------------
# Slot Update Serializer
# -------------------------------
class ExpertSlotUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertSlot
        fields = [
            "start_datetime",
            "end_datetime",
            "price",
            "requires_approval",
            "status"
        ]

    def validate(self, attrs):
        if "start_datetime" in attrs and "end_datetime" in attrs:
            if attrs["end_datetime"] <= attrs["start_datetime"]:
                raise serializers.ValidationError("End time must be after start time.")
        return attrs
