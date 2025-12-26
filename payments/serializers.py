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
