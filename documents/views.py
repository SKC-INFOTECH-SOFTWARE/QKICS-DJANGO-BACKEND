from django.shortcuts import get_object_or_404
from django.http import FileResponse

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status, generics

from .models import Document, DocumentDownload
from .serializers import (
    DocumentListSerializer,
    DocumentDetailSerializer,
)
from .services.access import can_user_download_document


# =====================================================
# DOCUMENT LIST VIEW
# =====================================================
class DocumentListView(generics.ListAPIView):
    """
    Lists all active documents.
    """
    permission_classes = [AllowAny]
    serializer_class = DocumentListSerializer

    def get_queryset(self):
        return Document.objects.filter(is_active=True).order_by("-created_at")


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
