from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CallRoom, CallMessage, CallRecording, CallNote

User = get_user_model()


class CallUserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ["id", "uuid", "username", "first_name", "last_name", "profile_picture"]


class CallMessageSerializer(serializers.ModelSerializer):
    sender   = CallUserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    is_mine  = serializers.SerializerMethodField()

    class Meta:
        model            = CallMessage
        fields           = ["id", "sender", "text", "file_url", "file_name", "file_size_bytes", "created_at", "is_mine"]
        read_only_fields = fields

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None

    def get_is_mine(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.sender_id == request.user.id
        return False


class CallRoomSerializer(serializers.ModelSerializer):
    user             = CallUserSerializer(read_only=True)
    advisor          = CallUserSerializer(read_only=True)
    duration_seconds = serializers.IntegerField(read_only=True)
    can_join         = serializers.SerializerMethodField()

    class Meta:
        model            = CallRoom
        fields           = [
            "id", "status", "user", "advisor",
            "scheduled_start", "scheduled_end",
            "started_at", "ended_at",
            "duration_seconds", "can_join", "created_at",
        ]
        read_only_fields = fields

    def get_can_join(self, obj):
        return obj.can_join()


class CallNoteSerializer(serializers.ModelSerializer):
    room_id         = serializers.UUIDField(source="room.id", read_only=True)
    scheduled_start = serializers.DateTimeField(source="room.scheduled_start", read_only=True)
    other_person    = serializers.SerializerMethodField()

    class Meta:
        model            = CallNote
        fields           = ["id", "room_id", "other_person", "scheduled_start", "content", "created_at", "updated_at"]
        read_only_fields = ["id", "room_id", "other_person", "scheduled_start", "created_at", "updated_at"]

    def get_other_person(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        user  = request.user
        room  = obj.room
        other = room.advisor if room.user_id == user.id else room.user
        return other.get_full_name() or other.username


class CallRecordingAdminSerializer(serializers.ModelSerializer):
    room_id          = serializers.UUIDField(source="room.id", read_only=True)
    user_username    = serializers.CharField(source="room.user.username", read_only=True)
    advisor_username = serializers.CharField(source="room.advisor.username", read_only=True)
    file_size_mb     = serializers.SerializerMethodField()

    class Meta:
        model            = CallRecording
        fields           = [
            "id", "room_id", "user_username", "advisor_username",
            "status", "egress_id",
            "cloudinary_public_id",
            "file_size_bytes", "file_size_mb", "duration_seconds",
            "started_at", "ended_at", "delete_after", "deleted_at",
        ]
        read_only_fields = fields

    def get_file_size_mb(self, obj):
        if obj.file_size_bytes:
            return round(obj.file_size_bytes / 1024 / 1024, 2)
        return None
