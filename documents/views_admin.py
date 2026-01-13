from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from users.permissions import IsAdmin
from .models import Document
from .serializers_admin import AdminDocumentSerializer


class AdminDocumentCreateView(generics.CreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminDocumentSerializer

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class AdminDocumentListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminDocumentSerializer

    def get_queryset(self):
        return Document.objects.all().order_by("-created_at")


class AdminDocumentUpdateView(generics.UpdateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminDocumentSerializer
    lookup_field = "uuid"

    def get_queryset(self):
        return Document.objects.all()


class AdminDocumentToggleStatusView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, uuid):
        document = get_object_or_404(Document, uuid=uuid)

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
            },
            status=status.HTTP_200_OK,
        )
