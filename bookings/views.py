import uuid
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ExpertSlot, Booking
from .serializers import (
    ExpertSlotSerializer,
    BookingCreateSerializer,
    BookingSerializer,
    BookingApprovalSerializer,
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