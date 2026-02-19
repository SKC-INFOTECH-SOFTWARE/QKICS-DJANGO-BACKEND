from django.urls import path
from .views.users import AdminUserListView
from .views.experts import (
    AdminExpertApplicationListView,
    AdminExpertApplicationUpdateView,
)
from .views.entrepreneurs import (
    AdminEntrepreneurApplicationListView,
    AdminEntrepreneurApplicationUpdateView,
)

urlpatterns = [
    # Admin user management
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    # Admin expert application management
    path(
        "experts/applications/",
        AdminExpertApplicationListView.as_view(),
        name="admin-expert-applications",
    ),
    path(
        "experts/applications/<int:profile_id>/",
        AdminExpertApplicationUpdateView.as_view(),
        name="admin-expert-application-update",
    ),
    # Admin entrepreneur application management
    path(
        "entrepreneurs/applications/",
        AdminEntrepreneurApplicationListView.as_view(),
        name="admin-entrepreneur-applications",
    ),
    path(
        "entrepreneurs/applications/<int:profile_id>/",
        AdminEntrepreneurApplicationUpdateView.as_view(),
        name="admin-entrepreneur-application-update",
    ),
]
