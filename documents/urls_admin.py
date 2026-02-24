from django.urls import path
from .views_admin import (
    AdminDocumentCreateView,
    AdminDocumentListView,
    AdminDocumentUpdateView,
    AdminDocumentToggleStatusView,
    AdminDocumentPlatformSettingsView,
)

urlpatterns = [
    path(
        "admin/upload/",
        AdminDocumentCreateView.as_view(),
        name="admin-document-upload",
    ),
    path(
        "admin/list/",
        AdminDocumentListView.as_view(),
        name="admin-document-list",
    ),
    path(
        "admin/<uuid:uuid>/update/",
        AdminDocumentUpdateView.as_view(),
        name="admin-document-update",
    ),
    path(
        "admin/<uuid:uuid>/toggle-status/",
        AdminDocumentToggleStatusView.as_view(),
        name="admin-document-toggle-status",
    ),
    path(
        "admin/settings/",
        AdminDocumentPlatformSettingsView.as_view(),
        name="admin-document-platform-settings",
    ),
]
