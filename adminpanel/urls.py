from django.urls import path
from .views.users import AdminUserListView
from .views.experts import (
    AdminExpertApplicationListView,
    AdminExpertApplicationUpdateView,
)
urlpatterns = [
    # Admin user management
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    # Admin expert application management
    path("experts/applications/", AdminExpertApplicationListView.as_view(), name="admin-expert-applications"),
    path("experts/applications/<int:profile_id>/", AdminExpertApplicationUpdateView.as_view(), name="admin-expert-application-update"),
]
