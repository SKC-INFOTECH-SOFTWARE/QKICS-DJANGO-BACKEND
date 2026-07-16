from rest_framework import serializers
from .models import Payment


# ============================================================
# READ SERIALIZER (List / Detail)
# ============================================================


class PaymentSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for listing and viewing payments.
    """

    class Meta:
        model = Payment
        fields = [
            "uuid",
            "purpose",
            "reference_id",
            "amount",
            "status",
            "gateway",
            "gateway_order_id",
            "gateway_payment_id",
            "created_at",
        ]
        read_only_fields = fields


# ============================================================
# FAKE BOOKING PAYMENT SERIALIZER
# ============================================================


class FakeBookingPaymentSerializer(serializers.Serializer):
    """
    Used only to simulate a booking payment.
    """

    booking_id = serializers.UUIDField()

    def validate_booking_id(self, value):
        # Validation against Booking will be added later
        # (keeping payments app decoupled for now)
        return value


# ============================================================
# GENERIC PAYMENT INITIATION (gateway-agnostic)
# ============================================================


class InitiatePaymentSerializer(serializers.Serializer):
    """
    Start a payment for any purpose through the configured gateway.

    - BOOKING       -> requires booking_id (the Booking uuid)
    - SUBSCRIPTION  -> requires plan_uuid (the SubscriptionPlan uuid)
    """

    purpose = serializers.ChoiceField(
        choices=[Payment.PURPOSE_BOOKING, Payment.PURPOSE_SUBSCRIPTION]
    )
    booking_id = serializers.UUIDField(required=False)
    plan_uuid = serializers.UUIDField(required=False)

    def validate(self, attrs):
        purpose = attrs["purpose"]
        if purpose == Payment.PURPOSE_BOOKING and not attrs.get("booking_id"):
            raise serializers.ValidationError(
                {"booking_id": "booking_id is required for a booking payment."}
            )
        if purpose == Payment.PURPOSE_SUBSCRIPTION and not attrs.get("plan_uuid"):
            raise serializers.ValidationError(
                {"plan_uuid": "plan_uuid is required for a subscription payment."}
            )
        return attrs
