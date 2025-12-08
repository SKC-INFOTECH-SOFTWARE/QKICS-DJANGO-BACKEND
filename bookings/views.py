import uuid
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ExpertSlot, Booking, BookingPayment, BookingReview
from .serializers import (
    ExpertSlotSerializer,
    BookingCreateSerializer,
    BookingSerializer,
    BookingApprovalSerializer,
    BookingPaymentCreateSerializer,
    BookingPaymentUpdateSerializer,
    BookingReviewSerializer,
)

# If Razorpay needed:
# import razorpay
# razorpay_client = razorpay.Client(auth=("KEY", "SECRET"))


# --------------------------
# List Active Slots for a Given Expert
# --------------------------
class ExpertSlotListView(generics.ListAPIView):
    serializer_class = ExpertSlotSerializer

    def get_queryset(self):
        expert_id = self.kwargs["expert_id"]
        return ExpertSlot.objects.filter(
            expert_id=expert_id,
            status="ACTIVE",
            start_datetime__gte=timezone.now()
        ).order_by("start_datetime")


# --------------------------
# Create Booking (User)
# --------------------------
class BookingCreateView(generics.CreateAPIView):
    serializer_class = BookingCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        return Response(BookingSerializer(booking).data, status=201)


# --------------------------
# Booking List - for User or Expert
# --------------------------
class BookingListView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        as_expert = self.request.query_params.get("as_expert")

        if as_expert == "true":
            return Booking.objects.filter(expert=user).order_by("-created_at")

        return Booking.objects.filter(user=user).order_by("-created_at")


# --------------------------
# Booking Detail
# --------------------------
class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Booking.objects.all()
    lookup_field = "id"


# --------------------------
# Expert Approves or Declines Booking
# --------------------------
class BookingApprovalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=404)

        # Only expert can take action
        if booking.expert != request.user:
            raise PermissionDenied("You are not the expert for this booking.")

        if booking.status != Booking.STATUS_PENDING:
            raise ValidationError("Booking is not awaiting approval.")

        serializer = BookingApprovalSerializer(
            data=request.data,
            context={"booking": booking}
        )
        serializer.is_valid(raise_exception=True)

        approve = serializer.validated_data["approve"]

        if approve:
            booking.status = Booking.STATUS_AWAITING_PAYMENT
            booking.expert_approved_at = timezone.now()
            booking.save()
            return Response({"detail": "Booking approved"}, status=200)
        else:
            booking.status = Booking.STATUS_DECLINED
            booking.save()
            return Response({"detail": "Booking declined"}, status=200)


# --------------------------
# Create Razorpay Order (Payment Init)
# --------------------------
class BookingPaymentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=404)

        if booking.user != request.user:
            raise PermissionDenied("Not your booking.")

        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            raise ValidationError("Booking is not ready for payment.")

        # ---- Razorpay Order Creation (Uncomment when keys available) ----
        # order = razorpay_client.order.create({
        #     "amount": int(booking.price * 100),  # Razorpay uses paise
        #     "currency": "INR",
        #     "receipt": str(booking.id),
        # })

        # Simulated order for now:
        order = {
            "id": str(uuid.uuid4()),
            "amount": float(booking.price),
            "currency": "INR"
        }

        payment = BookingPayment.objects.create(
            booking=booking,
            user=request.user,
            amount=booking.price,
            order_id=order["id"],
            status=BookingPayment.STATUS_CREATED,
        )

        return Response({
            "order": order,
            "payment": BookingPaymentCreateSerializer(payment).data
        }, status=201)


# --------------------------
# Payment Confirm (Webhook or Client)
# --------------------------
class BookingPaymentConfirmView(APIView):
    permission_classes = [permissions.AllowAny]  # Webhook-safe, but secure with signature logic

    def post(self, request):
        serializer = BookingPaymentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data["order_id"]
        payment_id = serializer.validated_data["payment_id"]
        signature = serializer.validated_data["payment_signature"]

        # Retrieve payment
        try:
            payment = BookingPayment.objects.get(order_id=order_id)
        except BookingPayment.DoesNotExist:
            return Response({"detail": "Payment not found"}, status=404)

        booking = payment.booking

        # ---- Razorpay Signature Verification (Uncomment) ----
        # import razorpay
        # try:
        #     razorpay_client.utility.verify_payment_signature({
        #         "razorpay_order_id": order_id,
        #         "razorpay_payment_id": payment_id,
        #         "razorpay_signature": signature,
        #     })
        # except:
        #     return Response({"detail": "Invalid signature"}, status=400)

        # Update payment
        payment.payment_id = payment_id
        payment.payment_signature = signature
        payment.status = BookingPayment.STATUS_SUCCESS
        payment.paid_at = timezone.now()
        payment.save()

        # Update booking state
        booking.status = Booking.STATUS_PAID
        booking.paid_at = timezone.now()
        booking.confirmed_at = timezone.now()
        booking.chat_room_id = uuid.uuid4()
        booking.status = Booking.STATUS_CONFIRMED
        booking.save()

        return Response({"detail": "Payment successful, booking confirmed"}, status=200)


# --------------------------
# Submit Review
# --------------------------
class BookingReviewCreateView(generics.CreateAPIView):
    serializer_class = BookingReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        booking_id = self.kwargs["booking_id"]

        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            raise ValidationError("Booking not found.")

        return {
            "booking": booking,
            "request": self.request,
        }
