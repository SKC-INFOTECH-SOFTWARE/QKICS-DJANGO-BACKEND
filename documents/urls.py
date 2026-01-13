from django.urls import path, include
from . import urls_admin as admin_urls

from .views import (
    DocumentListView,
    DocumentDetailView,
    DocumentDownloadView,
    MyDocumentDownloadsView,
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
    path("", include(admin_urls)),
]
