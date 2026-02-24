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
# =====================================================
# DOCUMENT LIST
# ===================================================
class DocumentListView(generics.ListAPIView):
    """
    Lists all active documents (Cursor paginated).
    """

    permission_classes = [AllowAny]
    serializer_class = DocumentListSerializer
    pagination_class = DocumentCursorPagination

    def get_queryset(self):
        return (
            Document.objects
            .filter(is_active=True)
            .order_by("-created_at")
        )


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
    """
    Handles document download with access control.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        # 1. Fetch document
        document = get_object_or_404(
            Document,
            uuid=uuid,
            is_active=True,
        )

        # 2. Access check
        allowed, reason = can_user_download_document(
            request.user,
            document,
        )

        if not allowed:
            return Response(
                {"detail": reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        # 3. Create download history
        DocumentDownload.objects.create(
            user=request.user,
            document=document,
            access_type_snapshot=document.access_type,
        )

        # 4. Return file
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.file.name,
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

    def get_queryset(self):
        return (
            DocumentDownload.objects.select_related("document")
            .filter(user=self.request.user)
        )


# =====================================================
# USER DOCUMENT CREATE VIEW
# =====================================================
class UserDocumentCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserDocumentCreateSerializer

    def perform_create(self, serializer):
        user = self.request.user

        # Admin unlimited
        if user.is_superuser:
            serializer.save(uploaded_by=user)
            return

        settings_obj, _ = DocumentPlatformSettings.objects.get_or_create(id=1)

        now = timezone.now()
        first_day = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        monthly_count = Document.objects.filter(
            uploaded_by=user,
            created_at__gte=first_day
        ).count()

        if monthly_count >= settings_obj.monthly_upload_limit:
            raise ValidationError(
                f"Monthly upload limit ({settings_obj.monthly_upload_limit}) reached."
            )

        serializer.save(uploaded_by=user)