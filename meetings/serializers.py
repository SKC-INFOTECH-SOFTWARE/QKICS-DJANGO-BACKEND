from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from meetings.models import Meeting, MeetingInvite

User = get_user_model()


class MeetingHostSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "profile_picture"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class MeetingInviteSerializer(serializers.ModelSerializer):
    user = MeetingHostSerializer(read_only=True)
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = MeetingInvite
        fields = [
            "id",
            "user",
            "email",
            "name",
            "display_name",
            "invited_at",
            "joined_at",
        ]


class AdminMeetingSerializer(serializers.ModelSerializer):
    """Full meeting record for the admin panel, including the shareable link."""

    host = MeetingHostSerializer(read_only=True)
    invite_link = serializers.SerializerMethodField()
    room_id = serializers.SerializerMethodField()
    invited_count = serializers.SerializerMethodField()
    joined_count = serializers.SerializerMethodField()
    can_join_now = serializers.SerializerMethodField()
    link_expires_at = serializers.DateTimeField(read_only=True)
    recording_retention_days = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "host",
            "invite_token",
            "invite_link",
            "access_mode",
            "scheduled_start",
            "scheduled_end",
            "max_participants",
            "require_host",
            "allow_guests",
            "status",
            "room_id",
            "invited_count",
            "joined_count",
            "can_join_now",
            "link_expires_at",
            "recording_retention_days",
            "created_at",
            "updated_at",
        ]

    def get_invite_link(self, obj):
        from meetings.services.meeting_service import build_invite_link

        return build_invite_link(obj, self.context.get("request"))

    def get_room_id(self, obj):
        return str(obj.call_room_id) if obj.call_room_id else None

    def get_invited_count(self, obj):
        count = getattr(obj, "invited_count_annotated", None)
        return count if count is not None else obj.invites.count()

    def get_joined_count(self, obj):
        count = getattr(obj, "joined_count_annotated", None)
        if count is not None:
            return count
        return obj.invites.filter(joined_at__isnull=False).count()

    def get_can_join_now(self, obj):
        return obj.can_join_now()

    def get_recording_retention_days(self, obj):
        return Meeting.RECORDING_RETENTION_DAYS


class AdminMeetingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = [
            "title",
            "description",
            "access_mode",
            "scheduled_start",
            "scheduled_end",
            "max_participants",
            "require_host",
            "allow_guests",
        ]

    def validate_max_participants(self, value):
        if value < 2 or value > 100:
            raise serializers.ValidationError(
                "max_participants must be between 2 and 100."
            )
        return value

    def validate(self, attrs):
        start = attrs.get("scheduled_start")
        end = attrs.get("scheduled_end")

        if end and not start:
            raise serializers.ValidationError(
                {"scheduled_start": "Provide a start time when setting an end time."}
            )
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"scheduled_end": "End time must be after the start time."}
            )
        if start and not end:
            raise serializers.ValidationError(
                {"scheduled_end": "Provide an end time for a scheduled meeting."}
            )
        if end and end < timezone.now():
            raise serializers.ValidationError(
                {"scheduled_end": "The end time is already in the past."}
            )
        return attrs


class AdminMeetingUpdateSerializer(AdminMeetingCreateSerializer):
    class Meta(AdminMeetingCreateSerializer.Meta):
        pass

    def validate(self, attrs):
        # On a PATCH, validate against the merged record, not just the payload.
        merged = {
            "scheduled_start": attrs.get(
                "scheduled_start", self.instance.scheduled_start
            ),
            "scheduled_end": attrs.get("scheduled_end", self.instance.scheduled_end),
        }
        start, end = merged["scheduled_start"], merged["scheduled_end"]
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"scheduled_end": "End time must be after the start time."}
            )
        if (start and not end) or (end and not start):
            raise serializers.ValidationError(
                {"scheduled_end": "A scheduled meeting needs both a start and an end."}
            )
        if "max_participants" in attrs:
            self.validate_max_participants(attrs["max_participants"])
        return attrs


class MeetingInviteCreateSerializer(serializers.Serializer):
    """Invite registered users by id and/or outsiders by email."""

    user_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list
    )
    emails = serializers.ListField(
        child=serializers.EmailField(), required=False, default=list
    )
    send_email = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if not attrs.get("user_ids") and not attrs.get("emails"):
            raise serializers.ValidationError(
                "Provide at least one user or email address."
            )
        return attrs


class PublicMeetingSerializer(serializers.ModelSerializer):
    """What the pre-join page may see. Deliberately minimal — no invite token,
    no host email, nothing about other participants."""

    host_name = serializers.SerializerMethodField()
    can_join_now = serializers.SerializerMethodField()
    join_opens_at = serializers.SerializerMethodField()
    requires_invite = serializers.SerializerMethodField()
    is_recorded = serializers.SerializerMethodField()
    allows_guests = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "host_name",
            "scheduled_start",
            "scheduled_end",
            "status",
            "can_join_now",
            "join_opens_at",
            "requires_invite",
            "is_recorded",
            "allows_guests",
        ]

    def get_host_name(self, obj):
        return obj.host.get_full_name() or obj.host.username

    def get_can_join_now(self, obj):
        return obj.can_join_now()

    def get_join_opens_at(self, obj):
        return obj.join_opens_at()

    def get_requires_invite(self, obj):
        return obj.access_mode == Meeting.INVITED_ONLY

    def get_is_recorded(self, obj):
        return True  # every meeting is recorded

    def get_allows_guests(self, obj):
        """Whether someone with no Qkics account can join by typing a name."""
        return obj.allow_guests and obj.access_mode == Meeting.ANYONE_WITH_LINK
