from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Post, Comment, Tag, PostMedia
from subscriptions.services.access import is_user_premium  #  (subscription)
from django.db.models import Max
import mimetypes

User = get_user_model()


# =====================================================
# AUTHOR SERIALIZER (UNCHANGED)
# =====================================================


class AuthorSerializer(serializers.ModelSerializer):
    user_type_display = serializers.CharField(
        source="get_user_type_display", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "user_type",
            "user_type_display",
            "profile_picture",
        ]


# =====================================================
# TAG SERIALIZER (UNCHANGED)
# =====================================================


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = [
            "id",
            "name",
            "slug",
        ]


# =====================================================
# REPLY SERIALIZER
# (ONLY content rendering changed for subscription)
# =====================================================


class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()

    #  (subscription-based rendering)
    content = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "total_likes",
            "is_liked",
            "created_at",
        ]

    #  (subscription logic only)
    def get_content(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if user and user.is_authenticated and obj.author_id == user.id:
            return obj.full_content or obj.content

        if user and user.is_authenticated and is_user_premium(user):
            return obj.full_content or obj.content

        return obj.preview_content or obj.content

    # UNCHANGED
    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.comment_likes.filter(user=user).exists()


# =====================================================
# COMMENT SERIALIZER
# (ONLY content rendering changed for subscription)
# =====================================================


class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()
    total_replies = serializers.IntegerField(
        source="total_replies_count", read_only=True
    )

    #  (subscription-based rendering)
    content = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "total_likes",
            "is_liked",
            "total_replies",
            "created_at",
        ]

    #  (subscription logic only)
    def get_content(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if user and user.is_authenticated and obj.author_id == user.id:
            return obj.full_content or obj.content

        if user and user.is_authenticated and is_user_premium(user):
            return obj.full_content or obj.content

        return obj.preview_content or obj.content

    # UNCHANGED
    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.comment_likes.filter(user=user).exists()


# =====================================================
# POST SERIALIZER
# (ONLY content rendering changed for subscription)
# =====================================================
class PostMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostMedia
        fields = [
            "id",
            "media_type",
            "file",
            "order",
            "created_at",
        ]
        read_only_fields = ["id", "media_type", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    total_comments = serializers.IntegerField(
        source="total_comments_count", read_only=True
    )
    is_liked = serializers.SerializerMethodField()

    #  (subscription-based rendering)
    content = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "content",
            "media",
            "tags",
            "knowledge_hub",
            "total_likes",
            "total_comments",
            "is_liked",
            "created_at",
            "updated_at",
        ]

    #  (subscription logic only)
    def get_content(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if user and user.is_authenticated and obj.author_id == user.id:
            return obj.full_content or obj.content

        if user and user.is_authenticated and is_user_premium(user):
            return obj.full_content or obj.content

        return obj.preview_content or obj.content

    # UNCHANGED
    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.post_likes.filter(user=user).exists()


# =====================================================
# POST SEARCH SERIALIZER
# (ONLY content rendering changed for subscription)
# =====================================================


class PostSearchSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    media = PostMediaSerializer(many=True, read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    total_comments = serializers.IntegerField(
        source="total_comments_count", read_only=True
    )
    is_liked = serializers.SerializerMethodField()
    content = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "content",
            "media",
            "tags",
            "knowledge_hub",
            "is_liked",
            "total_likes",
            "total_comments",
            "created_at",
        ]

    #
    def get_content(self, obj):
        request = self.context.get("request")
        user = request.user if request else None

        if user and user.is_authenticated and obj.author_id == user.id:
            return obj.full_content or obj.content

        if user and user.is_authenticated and is_user_premium(user):
            return obj.full_content or obj.content

        return obj.preview_content or obj.content

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.post_likes.filter(user=user).exists()


# =====================================================
# CREATE / UPDATE SERIALIZERS
# (ONLY field names changed, logic untouched)
# =====================================================


class PostCreateSerializer(serializers.ModelSerializer):
    media_files = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )

    class Meta:
        model = Post
        fields = [
            "title",
            "preview_content",
            "full_content",
            "tags",
            "knowledge_hub",
            "media_files",
        ]

    def validate(self, attrs):
        if not attrs.get("preview_content"):
            raise serializers.ValidationError(
                {"preview_content": "Preview content is required"}
            )
        if not attrs.get("full_content"):
            raise serializers.ValidationError(
                {"full_content": "Full content is required"}
            )
        return attrs

    def validate_media_files(self, files):
        if len(files) > 10:
            raise serializers.ValidationError("Maximum 10 files allowed per post.")
        return files

    def create(self, validated_data):
        media_files = validated_data.pop("media_files", [])
        tags = validated_data.pop("tags", [])

        with transaction.atomic():
            post = Post.objects.create(**validated_data)

            if tags:
                post.tags.set(tags)

            for index, file in enumerate(media_files):
                PostMedia.objects.create(post=post, file=file, order=index)

        return post


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = [
            "preview_content",
            "full_content",  #
            "parent",
        ]

    def validate(self, attrs):
        if not attrs.get("preview_content"):
            raise serializers.ValidationError(
                {"preview_content": "Preview content is required"}
            )
        if not attrs.get("full_content"):
            raise serializers.ValidationError(
                {"full_content": "Full content is required"}
            )
        return attrs


class PostUpdateSerializer(serializers.ModelSerializer):
    add_media = serializers.ListField(
        child=serializers.FileField(), write_only=True, required=False
    )
    remove_media_ids = serializers.JSONField(required=False)
    reorder_media = serializers.JSONField(required=False)

    class Meta:
        model = Post
        fields = [
            "title",
            "preview_content",
            "full_content",
            "knowledge_hub",
            "tags",
            "add_media",
            "remove_media_ids",
            "reorder_media",
        ]

    # -------------------------
    # MEDIA VALIDATION
    # -------------------------
    def validate_add_media(self, files):
        for file in files:
            mime_type, _ = mimetypes.guess_type(file.name)

            if not mime_type:
                raise serializers.ValidationError(
                    f"Could not determine file type for {file.name}"
                )

            # IMAGE → 20MB
            if mime_type.startswith("image"):
                if file.size > 20 * 1024 * 1024:
                    raise serializers.ValidationError(
                        f"{file.name} exceeds 20MB image limit."
                    )

            # VIDEO → 100MB
            elif mime_type.startswith("video"):
                if file.size > 100 * 1024 * 1024:
                    raise serializers.ValidationError(
                        f"{file.name} exceeds 100MB video limit."
                    )

            else:
                raise serializers.ValidationError(f"{file.name} is not supported.")

        return files

    # -------------------------
    # ATOMIC UPDATE
    # -------------------------
    def update(self, instance, validated_data):
        add_media = validated_data.pop("add_media", [])
        remove_ids = validated_data.pop("remove_media_ids", [])
        reorder_data = validated_data.pop("reorder_media", [])
        tags = validated_data.pop("tags", None)

        with transaction.atomic():

            # 🔹 Update text fields
            for attr, value in validated_data.items():
                setattr(instance, attr, value)

            instance.save()

            if tags is not None:
                instance.tags.set(tags)

            # 🔹 Remove selected media
            if remove_ids:
                instance.media.filter(id__in=remove_ids).delete()

            # 🔹 Reorder media
            for item in reorder_data:
                media = instance.media.filter(id=item.get("id")).first()
                if media:
                    media.order = item.get("order", media.order)
                    media.save()

            # 🔹 Max 10 media check
            current_count = instance.media.count()
            if current_count + len(add_media) > 10:
                raise serializers.ValidationError(
                    "Maximum 10 media files allowed per post."
                )

            # 🔹 Add new media
            current_max_order = (
                instance.media.aggregate(Max("order"))["order__max"] or 0
            )

            for index, file in enumerate(add_media):
                PostMedia.objects.create(
                    post=instance, file=file, order=current_max_order + index + 1
                )

        return instance
