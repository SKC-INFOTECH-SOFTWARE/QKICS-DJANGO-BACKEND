from rest_framework import serializers
from .models import Document, DocumentPlatformSettings


class AdminDocumentSerializer(serializers.ModelSerializer):
    """
    Admin serializer for creating & updating documents.
    """

    class Meta:
        model = Document
        fields = [
            "uuid",
            "title",
            "description",
            "file",
            "access_type",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["uuid", "created_at", "updated_at"]


class DocumentPlatformSettingsSerializer(serializers.ModelSerializer):

    class Meta:
        model = DocumentPlatformSettings
        fields = [
            "monthly_upload_limit",
            "monthly_download_limit",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
