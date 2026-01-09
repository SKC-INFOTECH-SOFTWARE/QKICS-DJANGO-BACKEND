from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import FakeBookingPaymentSerializer, PaymentSerializer
from .services.fake import FakePaymentService
from .models import Payment

from .services.fake import FakePaymentService
from .models import Payment

# ✅ ADD THIS IMPORT
from bookings.services.confirm_booking import confirm_booking_after_payment
from bookings.models import Booking

class FakeBookingPaymentView(APIView):
    """
    Fake payment endpoint for booking payments.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FakeBookingPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking_id = serializer.validated_data["booking_id"]

        booking = Booking.objects.get(uuid=booking_id, user=request.user)

        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            return Response(
                {"detail": "Booking is not awaiting payment"},
                status=400,
            )

        payment_service = FakePaymentService()

        payment = payment_service.create_payment(
            user=request.user,
            purpose=Payment.PURPOSE_BOOKING,
            reference_id=booking.uuid,
            amount=booking.price,
        )

        payment = payment_service.confirm_payment(payment=payment)

        confirm_booking_after_payment(payment=payment)

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )
