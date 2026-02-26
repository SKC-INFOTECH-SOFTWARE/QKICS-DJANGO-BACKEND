from django.urls import path, include
from . import urls_admin as admin_urls

from .views import (
    DocumentListView,
    DocumentDetailView,
    DocumentDownloadView,
    MyDocumentDownloadsView,
    UserDocumentCreateView,
    MyUploadedDocumentsView,
    UserDocumentUpdateView,
    UserDocumentToggleStatusView,
)

urlpatterns = [
    # -----------------------------
    # DOCUMENT LIST & DETAIL
    # -----------------------------
    path(
        "",
        DocumentListView.as_view(),
        name="document-list",
    ),
    path(
        "<uuid:uuid>/",
        DocumentDetailView.as_view(),
        name="document-detail",
    ),
    # -----------------------------
    # DOCUMENT DOWNLOAD
    # -----------------------------
    path(
        "<uuid:uuid>/download/",
        DocumentDownloadView.as_view(),
        name="document-download",
    ),
    # -----------------------------
    # MY DOWNLOADS
    # -----------------------------
    path(
        "my-downloads/",
        MyDocumentDownloadsView.as_view(),
        name="my-document-downloads",
    ),
    # -----------------------------
    # USER DOCUMENT UPLOAD
    # -----------------------------
    path(
        "upload/",
        UserDocumentCreateView.as_view(),
        name="user-document-upload",
    ),
    path("", include(admin_urls)),
    path(
        "my-documents/",
        MyUploadedDocumentsView.as_view(),
        name="my-uploaded-documents",
    ),
    path(
        "my-documents/<uuid:uuid>/update/",
        UserDocumentUpdateView.as_view(),
        name="user-document-update",
    ),
    path(
        "my-documents/<uuid:uuid>/toggle-status/",
        UserDocumentToggleStatusView.as_view(),
        name="user-document-toggle-status",
    ),
]
