from rest_framework import serializers
from .models import Post, Comment
from users.models import User


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


class ReplySerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    total_likes = serializers.IntegerField(source="total_likes", read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "author", "content", "total_likes", "is_liked", "created_at"]

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.comment_likes.filter(user=user).exists()


class CommentSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    replies = ReplySerializer(many=True, read_only=True)
    total_likes = serializers.IntegerField(source="total_likes", read_only=True)
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


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    comments = CommentSerializer(many=True, read_only=True, source="top_level_comments")
    total_likes = serializers.IntegerField(source="total_likes", read_only=True)
    total_comments = serializers.IntegerField(source="total_comments", read_only=True)
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "content",
            "image",
            "total_likes",
            "total_comments",
            "is_liked",
            "comments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.post_likes.filter(user=user).exists()


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ["title", "content", "image"]


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
