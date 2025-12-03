from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "profile_picture"]
        read_only_fields = fields


class ChatRoomSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    expert = UserSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            "id",
            "user",
            "expert",
            "created_at",
            "last_message_at",
            "last_message",
        ]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-timestamp").first()
        if not msg:
            return None
        return {
            "text": msg.text or "File attached",
            "timestamp": msg.timestamp.isoformat(),
            "sender": msg.sender.username,
        }


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id",
            "sender",
            "text",
            "file_url",
            "timestamp",
            "is_read",
            "is_mine",
        ]

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return request.user == obj.sender if request and request.user.is_authenticated else False