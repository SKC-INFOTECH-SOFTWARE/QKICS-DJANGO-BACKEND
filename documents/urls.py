from django.urls import path

from .views import (
    DocumentDownloadView,
)
from .views_list import (
    DocumentListView,
    DocumentDetailView,
)

urlpatterns = [
    # ----------------------------------
    # DOCUMENT LIST & DETAIL
    # ----------------------------------
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
    # ----------------------------------
    # DOCUMENT DOWNLOAD
    # ----------------------------------
    path(
        "<uuid:uuid>/download/",
        DocumentDownloadView.as_view(),
        name="document-download",
    ),
]
