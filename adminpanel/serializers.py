from rest_framework import serializers
from django.contrib.auth import get_user_model
from ads.models import Advertisement
from companies.models import Company, CompanyMember, CompanyPost
from community.models import Post, Comment

User = get_user_model()


class AdminFullUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ["password"]


class AdminAdvertisementSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField()

    class Meta:
        model = Advertisement
        fields = "__all__"


class AdminAdvertisementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        exclude = [
            "uuid",
            "media_type",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        return super().create(validated_data)


class AdminAdvertisementUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        exclude = [
            "uuid",
            "media_type",
            "created_by",
            "created_at",
            "updated_at",
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class AdminCompanySerializer(serializers.ModelSerializer):

    owner = AdminUserSerializer(read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "industry",
            "website",
            "location",
            "status",
            "owner",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "slug",
            "owner",
            "created_at",
            "updated_at",
        ]


class AdminCompanyMemberSerializer(serializers.ModelSerializer):

    user = AdminUserSerializer(read_only=True)

    class Meta:
        model = CompanyMember
        fields = ["id", "user", "role", "joined_at"]


class AdminCompanyPostSerializer(serializers.ModelSerializer):

    author = AdminUserSerializer(read_only=True)

    class Meta:
        model = CompanyPost
        fields = ["id", "author", "content", "created_at", "updated_at"]


class AdminPostSerializer(serializers.ModelSerializer):
    """Community feed post, admin/moderation view. Read-only over the wire —
    moderation state is changed through the dedicated moderate endpoint."""

    author = AdminUserSerializer(read_only=True)
    hidden_by = AdminUserSerializer(read_only=True)
    total_likes = serializers.SerializerMethodField()
    total_comments = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "content",
            "preview_content",
            "knowledge_hub",
            "is_hidden",
            "hidden_at",
            "hidden_by",
            "moderation_reason",
            "total_likes",
            "total_comments",
            "created_at",
            "updated_at",
        ]

    def get_total_likes(self, obj):
        # `mod_likes` is annotated by AdminPostListView; fall back to the model
        # property for single-object fetches that skip the annotation.
        value = getattr(obj, "mod_likes", None)
        return value if value is not None else obj.total_likes

    def get_total_comments(self, obj):
        value = getattr(obj, "mod_comments", None)
        return value if value is not None else obj.total_comments


class AdminCommentSerializer(serializers.ModelSerializer):
    """Community comment/reply, admin/moderation view."""

    author = AdminUserSerializer(read_only=True)
    hidden_by = AdminUserSerializer(read_only=True)
    total_likes = serializers.SerializerMethodField()
    is_reply = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "parent",
            "is_reply",
            "author",
            "content",
            "preview_content",
            "is_hidden",
            "hidden_at",
            "hidden_by",
            "moderation_reason",
            "total_likes",
            "created_at",
            "updated_at",
        ]

    def get_total_likes(self, obj):
        value = getattr(obj, "mod_likes", None)
        return value if value is not None else obj.total_likes

    def get_is_reply(self, obj):
        return obj.parent_id is not None
