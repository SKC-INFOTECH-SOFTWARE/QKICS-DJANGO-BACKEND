from rest_framework import serializers
from .models import Document


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
