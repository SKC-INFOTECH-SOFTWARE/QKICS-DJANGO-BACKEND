from django.urls import path
from .views import (
    ExpertSlotListView,
    BookingListCreateView,
    BookingDetailView,
    BookingApprovalView,
    ExpertSlotCreateView,
    ExpertSlotUpdateView,
    ExpertSlotDeleteView,
)

urlpatterns = [
    # Slots
    path(
        "expert/<uuid:expert_id>/slots/",
        ExpertSlotListView.as_view(),
        name="expert-slots",
    ),
    path(
        "slots/",
        ExpertSlotCreateView.as_view(),
        name="slot-create",
    ),
    path(
        "slots/<uuid:uuid>/update/",
        ExpertSlotUpdateView.as_view(),
        name="slot-update",
    ),
    path(
        "slots/<uuid:uuid>/delete/",
        ExpertSlotDeleteView.as_view(),
        name="slot-delete",
    ),

    # Bookings
    path(
        "",
        BookingListCreateView.as_view(),
        name="booking-list-create",
    ),
    path(
        "<uuid:uuid>/",
        BookingDetailView.as_view(),
        name="booking-detail",
    ),
    path(
        "<uuid:booking_id>/approve/",
        BookingApprovalView.as_view(),
        name="booking-approve",
    ),
]
