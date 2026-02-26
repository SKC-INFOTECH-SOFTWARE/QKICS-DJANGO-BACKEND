from django.shortcuts import get_object_or_404
from django.http import FileResponse

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework import serializers
from .models import Document, DocumentDownload
from .serializers import (
    DocumentListSerializer,
    DocumentDetailSerializer,
    DocumentDownloadSerializer,
    UserDocumentCreateSerializer,
)
from .services.access import can_user_download_document
from .pagination import DocumentCursorPagination
from django.utils import timezone
from datetime import datetime
from rest_framework.exceptions import ValidationError
from .models import DocumentPlatformSettings
from django_filters.rest_framework import DjangoFilterBackend
from .services.limits import enforce_upload_limit, enforce_download_limit
from rest_framework.filters import SearchFilter, OrderingFilter


# =====================================================
# DOCUMENT LIST
# ===================================================
class DocumentListView(generics.ListAPIView):
    """
    Lists all active documents (Cursor paginated).
    Supports filtering, searching and ordering.
    """

    permission_classes = [AllowAny]
    serializer_class = DocumentListSerializer
    pagination_class = DocumentCursorPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "access_type",
        "uploaded_by",
    ]

    search_fields = [
        "title",
        "description",
    ]

    ordering_fields = [
        "created_at",
        "access_type",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        return Document.objects.filter(is_active=True)


# =====================================================
# DOCUMENT DETAIL VIEW
# =====================================================
class DocumentDetailView(generics.RetrieveAPIView):
    """
    Returns document metadata.
    """

    permission_classes = [AllowAny]
    serializer_class = DocumentDetailSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        return Document.objects.filter(is_active=True)


# =====================================================
# DOCUMENT DOWNLOAD VIEW
# =====================================================


class DocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):

        document = get_object_or_404(
            Document,
            uuid=uuid,
            is_active=True,
        )

        allowed, reason = can_user_download_document(
            request.user,
            document,
        )

        if not allowed:
            return Response(
                {"detail": reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            enforce_download_limit(request.user)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_403_FORBIDDEN,
            )

        DocumentDownload.objects.create(
            user=request.user,
            document=document,
            access_type_snapshot=document.access_type,
        )

        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.file.name.split("/")[-1],
        )


# =====================================================
# MY DOWNLOADS VIEW
# =====================================================
class MyDocumentDownloadsView(generics.ListAPIView):
    """
    Returns the authenticated user's document download history.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocumentDownloadSerializer
    pagination_class = DocumentCursorPagination

    def get_queryset(self):
        return (
            DocumentDownload.objects.select_related("document")
            .filter(user=self.request.user)
            .order_by("-downloaded_at")
        )


# =====================================================
# USER DOCUMENT CREATE VIEW
# =====================================================
class UserDocumentCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserDocumentCreateSerializer

    def perform_create(self, serializer):
        user = self.request.user

        try:
            enforce_upload_limit(user)
        except Exception as e:
            raise ValidationError(str(e))

        serializer.save(uploaded_by=user)


class MyUploadedDocumentsView(generics.ListAPIView):
    """
    Lists documents uploaded by the authenticated user.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocumentListSerializer
    pagination_class = DocumentCursorPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "access_type",
        "is_active",
    ]

    search_fields = [
        "title",
        "description",
    ]

    ordering_fields = [
        "created_at",
    ]

    ordering = ["-created_at"]

    def get_queryset(self):
        return Document.objects.filter(uploaded_by=self.request.user)


class UserDocumentUpdateView(generics.UpdateAPIView):
    """
    Allows user to update their own document.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserDocumentCreateSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        return Document.objects.filter(uploaded_by=self.request.user)


class UserDocumentToggleStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, uuid):

        document = get_object_or_404(Document, uuid=uuid, uploaded_by=request.user)

        is_active = request.data.get("is_active")

        if is_active is None:
            return Response(
                {"detail": "is_active field is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        document.is_active = is_active
        document.save(update_fields=["is_active"])

        return Response(
            {
                "uuid": document.uuid,
                "is_active": document.is_active,
                "message": "Document status updated",
            }
        )
