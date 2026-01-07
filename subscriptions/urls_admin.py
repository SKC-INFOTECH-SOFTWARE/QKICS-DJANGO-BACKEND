from django.urls import path
from .views_admin import (
    AdminSubscriptionPlanListCreateView,
    AdminSubscriptionPlanDetailView,
)

urlpatterns = [
    path(
        "admin/plans/",
        AdminSubscriptionPlanListCreateView.as_view(),
        name="admin-subscription-plan-list-create",
    ),
    path(
        "admin/plans/<uuid:uuid>/",
        AdminSubscriptionPlanDetailView.as_view(),
        name="admin-subscription-plan-detail",
    ),
]
