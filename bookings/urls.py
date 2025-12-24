from django.urls import path
from .views import (
    ExpertSlotListView,
    ExpertSlotCreateView,
    ExpertSlotUpdateView,
    ExpertSlotDeleteView,
    BookingListCreateView,
    BookingDetailView,
    BookingApprovalView,
)

urlpatterns = [
    # =======================
    # SLOTS
    # =======================
    path(
        "experts/<uuid:expert_id>/slots/",
        ExpertSlotListView.as_view(),
        name="expert-slots",
    ),
    path(
        "experts/slots/",
        ExpertSlotCreateView.as_view(),
        name="slot-create",
    ),
    path(
        "experts/slots/<uuid:id>/",
        ExpertSlotUpdateView.as_view(),
        name="slot-update",
    ),
    path(
        "experts/slots/<uuid:id>/delete/",
        ExpertSlotDeleteView.as_view(),
        name="slot-delete",
    ),
    # =======================
    # BOOKINGS
    # =======================
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
