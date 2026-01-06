from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Post, Comment, Tag
from subscriptions.services.access import is_user_premium  #  (subscription)

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
    total_replies = serializers.IntegerField(source="replies.count", read_only=True)

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


class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
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
            "image",
            "tags",
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
    total_likes = serializers.IntegerField(read_only=True)
    total_comments = serializers.IntegerField(
        source="total_comments_count", read_only=True
    )

    # 
    content = serializers.SerializerMethodField()

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


# =====================================================
# CREATE / UPDATE SERIALIZERS
# (ONLY field names changed, logic untouched)
# =====================================================


class PostCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = [
            "title",
            "preview_content",  # 
            "full_content",  # 
            "image",
            "tags",
        ]

    # Existing validations can stay exactly as you had them
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
