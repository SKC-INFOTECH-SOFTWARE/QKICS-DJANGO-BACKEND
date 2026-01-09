from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from payments.models import Payment
from payments.serializers import FakeBookingPaymentSerializer, PaymentSerializer
from payments.services.fake import FakePaymentService
from bookings.services.confirm_booking import confirm_booking_after_payment


class FakeBookingPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FakeBookingPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking_id = serializer.validated_data["booking_id"]

        booking = get_object_or_404(
            Booking,
            uuid=booking_id,
            user=request.user,
        )

        # FAKE auto-approve
        if booking.status == Booking.STATUS_PENDING:
            booking.status = Booking.STATUS_AWAITING_PAYMENT
            booking.save(update_fields=["status", "updated_at"])

        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            return Response(
                {"detail": f"Cannot pay for booking in {booking.status} state"},
                status=status.HTTP_400_BAD_REQUEST,
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

        booking.refresh_from_db()

        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "booking_id": str(booking.uuid),
                "chat_room_id": booking.chat_room_id,
                "status": "BOOKING_CONFIRMED_AND_CHAT_CREATED",
            },
            status=status.HTTP_201_CREATED,
        )
