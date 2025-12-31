from django.shortcuts import get_object_or_404
from django.http import FileResponse

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Document, DocumentDownload
from .services.access import can_user_download_document


class DocumentDownloadView(APIView):
    """
    Handles document download with access control.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, uuid):
        # -------------------------------------------------
        # 1. Fetch document
        # -------------------------------------------------
        document = get_object_or_404(
            Document,
            uuid=uuid,
            is_active=True,
        )

        # -------------------------------------------------
        # 2. Access check
        # -------------------------------------------------
        allowed, reason = can_user_download_document(
            request.user,
            document,
        )

        if not allowed:
            return Response(
                {"detail": reason},
                status=status.HTTP_403_FORBIDDEN,
            )

        # -------------------------------------------------
        # 3. Create download history
        # -------------------------------------------------
        DocumentDownload.objects.create(
            user=request.user,
            document=document,
            access_type_snapshot=document.access_type,
        )

        # -------------------------------------------------
        # 4. Return file
        # -------------------------------------------------
        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.file.name,
        )
        return response
