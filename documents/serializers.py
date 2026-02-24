from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Document, DocumentDownload

User = get_user_model()


# =====================================================
# DOCUMENT LIST SERIALIZER
# =====================================================
class DocumentListSerializer(serializers.ModelSerializer):
    """
    Used for listing documents.
    Does NOT expose file URL directly.
    """

    class Meta:
        model = Document
        fields = [
            "uuid",
            "title",
            "description",
            "access_type",
            "is_active",
            "created_at",
        ]


# =====================================================
# DOCUMENT DETAIL SERIALIZER
# =====================================================
class DocumentDetailSerializer(serializers.ModelSerializer):
    """
    Used for document detail page.
    File URL is exposed ONLY for detail view.
    """

    file_url = serializers.FileField(source="file", read_only=True)

    class Meta:
        model = Document
        fields = [
            "uuid",
            "title",
            "description",
            "access_type",
            "file_url",
            "created_at",
        ]


# =====================================================
# DOCUMENT DOWNLOAD HISTORY SERIALIZER
# =====================================================
class DocumentDownloadSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)

    class Meta:
        model = DocumentDownload
        fields = [
            "document_title",
            "access_type_snapshot",
            "downloaded_at",
        ]


# =====================================================
# USER DOCUMENT CREATE SERIALIZER
# =====================================================
class UserDocumentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for normal users uploading documents.
    Only FREE access_type allowed.
    """

    class Meta:
        model = Document
        fields = [
            "title",
            "description",
            "file",
            "access_type",
        ]

    def validate_access_type(self, value):
        if value != Document.AccessType.FREE:
            raise serializers.ValidationError(
                "You can only upload FREE documents."
            )
        return value