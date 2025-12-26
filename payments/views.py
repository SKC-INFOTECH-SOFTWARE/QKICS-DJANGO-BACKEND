from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import FakeBookingPaymentSerializer, PaymentSerializer
from .services.fake import FakePaymentService
from .models import Payment


class FakeBookingPaymentView(APIView):
    """
    Fake payment endpoint for booking payments.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FakeBookingPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking_id = serializer.validated_data["booking_id"]

        payment_service = FakePaymentService()

        # Step 1: create payment (INITIATED)
        payment = payment_service.create_payment(
            user=request.user,
            purpose=Payment.PURPOSE_BOOKING,
            reference_id=booking_id,
            amount=0,  # real amount will be enforced later from booking
        )

        # Step 2: confirm payment immediately (FAKE)
        payment = payment_service.confirm_payment(payment=payment)

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )
