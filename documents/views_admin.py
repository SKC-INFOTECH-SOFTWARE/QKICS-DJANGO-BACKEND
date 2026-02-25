from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from users.permissions import IsAdmin
from .models import Document
from .serializers_admin import AdminDocumentSerializer

from .pagination import DocumentCursorPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend


class AdminDocumentCreateView(generics.CreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminDocumentSerializer

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class AdminDocumentListView(generics.ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminDocumentSerializer
    pagination_class = DocumentCursorPagination

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_fields = [
        "access_type",
        "is_active",
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

    def get_queryset(self):
        return Document.objects.select_related("uploaded_by").order_by("-created_at")


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


# ===============================================
# DOCUMENT PLATFORM SETTINGS VIEW
# ===============================================
from .models import DocumentPlatformSettings
from .serializers_admin import DocumentPlatformSettingsSerializer


class AdminDocumentPlatformSettingsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        settings_obj, _ = DocumentPlatformSettings.objects.get_or_create(id=1)
        serializer = DocumentPlatformSettingsSerializer(settings_obj)
        return Response(serializer.data)

    def patch(self, request):
        settings_obj, _ = DocumentPlatformSettings.objects.get_or_create(id=1)

        serializer = DocumentPlatformSettingsSerializer(
            settings_obj, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
