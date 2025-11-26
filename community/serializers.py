from rest_framework import serializers
from .models import Post, Comment, Tag
from users.models import User


# ---------------------------
# AUTHOR
# ---------------------------
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
        ]


# ---------------------------
# TAG SERIALIZER
# ---------------------------
class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


# ---------------------------
# REPLY SERIALIZER
# ---------------------------
class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()

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

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.comment_likes.filter(user=user).exists()


# ---------------------------
# COMMENT SERIALIZER
# ---------------------------
class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()
    depth = serializers.IntegerField(read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "parent",
            "replies",
            "total_likes",
            "is_liked",
            "depth",
            "created_at",
        ]
        read_only_fields = ["replies", "depth", "created_at"]

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.comment_likes.filter(user=user).exists()


# ---------------------------
# POST SERIALIZER (SHOW TAGS)
# ---------------------------
class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True, source="top_level_comments")
    tags = TagSerializer(many=True, read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    total_comments = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "content",
            "image",
            "tags",
            "total_likes",
            "total_comments",
            "is_liked",
            "comments",
            "created_at",
            "updated_at",
        ]

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.post_likes.filter(user=user).exists()


# ---------------------------
# POST CREATE / UPDATE SERIALIZER (ACCEPT TAG IDs)
# ---------------------------
class PostCreateSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)
    tags = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )

    class Meta:
        model = Post
        fields = ["title", "content", "image", "tags"]

    def validate_tags(self, value):
        if not value:
            return []

        valid_ids = list(Tag.objects.filter(id__in=value).values_list("id", "name"))
        if len(valid_ids) != len(set(value)):
            raise serializers.ValidationError("Invalid tag IDs provided.")

        return value

    def create(self, validated_data):
        tag_ids = validated_data.pop("tags", [])
        post = Post.objects.create(**validated_data)
        if tag_ids:
            post.tags.set(tag_ids)
        return post

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop("tags", None)
        post = super().update(instance, validated_data)
        if tag_ids is not None:
            post.tags.set(tag_ids)
        return post


# ---------------------------
# COMMENT CREATE SERIALIZER
# ---------------------------
class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["content", "parent"]

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Comment cannot be empty.")
        if len(value) > 5000:
            raise serializers.ValidationError("Comment too long.")
        return value

    def validate_parent(self, value):
        if value and value.parent is not None:
            raise serializers.ValidationError("Cannot reply to a reply.")
        return value

    def create(self, validated_data):
        return Comment.objects.create(
            post=self.context["post"],
            author=self.context["request"].user,
            **validated_data
        )
