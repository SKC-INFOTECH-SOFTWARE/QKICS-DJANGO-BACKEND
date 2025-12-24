from django.utils import timezone
from django.db import transaction

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import ExpertSlot, Booking
from .serializers import (
    ExpertSlotSerializer,
    ExpertSlotCreateSerializer,
    ExpertSlotUpdateSerializer,
    BookingCreateSerializer,
    BookingSerializer,
    BookingApprovalSerializer,
)

# ============================================================
# SLOT VIEWS
# ============================================================


class ExpertSlotListView(generics.ListAPIView):
    """
    Public list of ACTIVE slots for a given expert.
    Used by users to view availability.
    """
    serializer_class = ExpertSlotSerializer
    pagination_class = None

    def get_queryset(self):
        expert_uuid = self.kwargs["expert_id"]
        return (
            ExpertSlot.objects
            .filter(
                expert__uuid=expert_uuid,
                status="ACTIVE",
                start_datetime__gt=timezone.now(),
            )
            .order_by("start_datetime")
        )


class ExpertSlotCreateView(generics.CreateAPIView):
    """
    Expert creates a new slot.
    """
    serializer_class = ExpertSlotCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(expert=self.request.user)


class ExpertSlotUpdateView(generics.UpdateAPIView):
    """
    Expert updates own slot.
    """
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


class ExpertSlotDeleteView(generics.DestroyAPIView):
    """
    Expert deletes own slot.
    """
    queryset = ExpertSlot.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "id"

    def perform_destroy(self, instance):
        if instance.expert != self.request.user:
            raise PermissionDenied("You cannot delete this slot.")

        if instance.has_active_bookings():
            raise ValidationError(
                "Cannot delete slot with active bookings. Disable it instead."
            )

        instance.delete()


# ============================================================
# BOOKING VIEWS
# ============================================================


class BookingListCreateView(generics.ListCreateAPIView):
    """
    - User: sees own bookings
    - Expert: sees bookings where they are expert (as_expert=true)
    - POST: create booking
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return (
            BookingCreateSerializer
            if self.request.method == "POST"
            else BookingSerializer
        )

    def get_queryset(self):
        user = self.request.user
        as_expert = self.request.query_params.get("as_expert")

        if as_expert == "true":
            return Booking.objects.filter(expert=user)

        return Booking.objects.filter(user=user)


class BookingDetailView(generics.RetrieveAPIView):
    """
    Retrieve booking by UUID.
    Only participant (user or expert) can access.
    """
    serializer_class = BookingSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Booking.objects.all()
    lookup_field = "uuid"

    def get_object(self):
        booking = super().get_object()
        user = self.request.user

        if booking.user != user and booking.expert != user:
            raise PermissionDenied("You do not have access to this booking.")

        return booking


class BookingApprovalView(APIView):
    """
    Expert approves or declines a PENDING booking.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, booking_id):
        try:
            booking = Booking.objects.select_for_update().get(uuid=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {"detail": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if booking.expert != request.user:
            raise PermissionDenied("You are not the expert for this booking.")

        if booking.status != Booking.STATUS_PENDING:
            raise ValidationError(
                f"Booking is not pending. Current status: {booking.status}"
            )

        serializer = BookingApprovalSerializer(
            data=request.data,
            context={"booking": booking},
        )
        serializer.is_valid(raise_exception=True)

        approve = serializer.validated_data["approve"]

        if approve:
            booking.status = Booking.STATUS_AWAITING_PAYMENT
            booking.expert_approved_at = timezone.now()
            booking.save(
                update_fields=[
                    "status",
                    "expert_approved_at",
                    "updated_at",
                ]
            )

            return Response(
                {"detail": "Booking approved. Awaiting payment."},
                status=status.HTTP_200_OK,
            )

        # Decline
        booking.status = Booking.STATUS_DECLINED
        booking.declined_at = timezone.now()
        booking.decline_reason = serializer.validated_data.get(
            "decline_reason", "Declined by expert"
        )
        booking.save(
            update_fields=[
                "status",
                "declined_at",
                "decline_reason",
                "updated_at",
            ]
        )

        return Response(
            {"detail": "Booking declined."},
            status=status.HTTP_200_OK,
        )
