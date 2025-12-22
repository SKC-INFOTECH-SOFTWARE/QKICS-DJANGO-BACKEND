import uuid
from django.utils import timezone
from rest_framework import generics, permissions, status
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
    ExpertSlotCreateSerializer,
    ExpertSlotUpdateSerializer,
)

# ============================================================
# SLOT VIEWS
# ============================================================


# List all slots for a given expert (used by users to view availability)
class ExpertSlotListView(generics.ListAPIView):
    serializer_class = ExpertSlotSerializer
    pagination_class = None

    def get_queryset(self):
        expert_uuid = self.kwargs["expert_id"]
        return ExpertSlot.objects.filter(expert__uuid=expert_uuid).order_by(
            "start_datetime"
        )


# Create a new slot by an expert
class ExpertSlotCreateView(generics.CreateAPIView):
    serializer_class = ExpertSlotCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(expert=self.request.user)


# Update an existing slot (only slot owner can update)
class ExpertSlotUpdateView(generics.UpdateAPIView):
    queryset = ExpertSlot.objects.all()
    serializer_class = ExpertSlotUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "id"

    def perform_update(self, serializer):
        slot = self.get_object()
        if slot.expert != self.request.user:
            raise PermissionDenied("You cannot update this slot.")
        serializer.save()


# Delete an existing slot (only slot owner can delete)
class ExpertSlotDeleteView(generics.DestroyAPIView):
    queryset = ExpertSlot.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "id"

    def perform_destroy(self, instance):
        if instance.expert != self.request.user:
            raise PermissionDenied("You cannot delete this slot.")
        instance.delete()


# ============================================================
# BOOKING VIEWS
# ============================================================


# List bookings for a user or expert and create a new booking
class BookingListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return BookingCreateSerializer
        return BookingSerializer

    def get_queryset(self):
        user = self.request.user
        as_expert = self.request.query_params.get("as_expert")

        if as_expert == "true":
            return Booking.objects.filter(expert=user)
        return Booking.objects.filter(user=user)


# Retrieve booking details using booking UUID
class BookingDetailView(generics.RetrieveAPIView):
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Booking.objects.all()
    lookup_field = "uuid"


# Expert approves or declines a booking request
class BookingApprovalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(uuid=booking_id)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=404)

        if booking.expert != request.user:
            raise PermissionDenied("You are not the expert for this booking.")

        if booking.status != Booking.STATUS_PENDING:
            raise ValidationError("Booking is not awaiting approval.")

        serializer = BookingApprovalSerializer(
            data=request.data, context={"booking": booking}
        )
        serializer.is_valid(raise_exception=True)

        approve = serializer.validated_data["approve"]

        if approve:
            booking.status = Booking.STATUS_AWAITING_PAYMENT
            booking.expert_approved_at = timezone.now()
            booking.save()
            return Response({"detail": "Booking approved"}, status=200)

        booking.status = Booking.STATUS_DECLINED
        booking.save()
        return Response({"detail": "Booking declined"}, status=200)


# ============================================================
# PAYMENT VIEWS
# ============================================================


# Create payment order for an approved booking
class BookingPaymentCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(uuid=booking_id)
        except Booking.DoesNotExist:
            return Response({"detail": "Booking not found"}, status=404)

        if booking.user != request.user:
            raise PermissionDenied("Not your booking.")

        if booking.status != Booking.STATUS_AWAITING_PAYMENT:
            raise ValidationError("Booking is not ready for payment.")

        order = {
            "id": str(uuid.uuid4()),
            "amount": float(booking.price),
            "currency": "INR",
        }

        payment = BookingPayment.objects.create(
            booking=booking,
            user=request.user,
            amount=booking.price,
            order_id=order["id"],
            status=BookingPayment.STATUS_CREATED,
        )

        return Response(
            {"order": order, "payment": BookingPaymentCreateSerializer(payment).data},
            status=201,
        )


# Confirm payment and activate booking session
class BookingPaymentConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = BookingPaymentUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = serializer.validated_data["order_id"]
        payment_id = serializer.validated_data["payment_id"]
        signature = serializer.validated_data["payment_signature"]

        try:
            payment = BookingPayment.objects.get(order_id=order_id)
        except BookingPayment.DoesNotExist:
            return Response({"detail": "Payment not found"}, status=404)

        booking = payment.booking

        payment.payment_id = payment_id
        payment.payment_signature = signature
        payment.status = BookingPayment.STATUS_SUCCESS
        payment.paid_at = timezone.now()
        payment.save()

        booking.status = Booking.STATUS_CONFIRMED
        booking.paid_at = timezone.now()
        booking.confirmed_at = timezone.now()
        booking.chat_room_id = uuid.uuid4()
        booking.save()

        return Response({"detail": "Payment successful, booking confirmed"}, status=200)


# ============================================================
# REVIEW VIEWS
# ============================================================


# Submit review for a completed booking
class BookingReviewCreateView(generics.CreateAPIView):
    serializer_class = BookingReviewSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_context(self):
        booking_id = self.kwargs["booking_id"]

        try:
            booking = Booking.objects.get(uuid=booking_id)
        except Booking.DoesNotExist:
            raise ValidationError("Booking not found.")

        return {
            "booking": booking,
            "request": self.request,
        }
