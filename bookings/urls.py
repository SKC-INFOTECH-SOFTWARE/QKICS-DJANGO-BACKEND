from django.urls import path
from .views import (
    ExpertSlotListView,
    BookingCreateView,
    BookingListView,
    BookingDetailView,
    BookingApprovalView,
    BookingPaymentCreateView,
    BookingPaymentConfirmView,
    BookingReviewCreateView,
    ExpertSlotCreateView,
    ExpertSlotUpdateView,
    ExpertSlotDeleteView
)

urlpatterns = [
    # Slot Views
    path("expert/<uuid:expert_id>/slots/", ExpertSlotListView.as_view(), name="expert-slots"),

    # Booking CRUD
    path("bookings/", BookingListView.as_view(), name="booking-list"),
    path("bookings/create/", BookingCreateView.as_view(), name="booking-create"),
    path("bookings/<uuid:id>/", BookingDetailView.as_view(), name="booking-detail"),

    # Expert approval
    path("bookings/<uuid:booking_id>/approve/", BookingApprovalView.as_view(), name="booking-approve"),

    # Payment
    path("bookings/<uuid:booking_id>/payment/create/", BookingPaymentCreateView.as_view(), name="payment-create"),
    path("payment/confirm/", BookingPaymentConfirmView.as_view(), name="payment-confirm"),

    # Reviews
    path("bookings/<uuid:booking_id>/review/", BookingReviewCreateView.as_view(), name="booking-review"),
    
    
    # Slot CRUD
    path("slots/create/", ExpertSlotCreateView.as_view(), name="slot-create"),
    path("slots/<uuid:id>/update/", ExpertSlotUpdateView.as_view(), name="slot-update"),
    path("slots/<uuid:id>/delete/", ExpertSlotDeleteView.as_view(), name="slot-delete"),
]
