from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for listing notifications to the frontend.
    Exposes only what the client needs.
    """

    class Meta:
        model = Notification
        fields = [
            "uuid",
            "event",
            "title",
            "body",
            "channels",
            "status",
            "is_read",
            "read_at",
            "data",
            "created_at",
        ]
        read_only_fields = fields
