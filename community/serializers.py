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
            "profile_picture",
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
    total_likes = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()
    total_replies = serializers.IntegerField(source="replies.count", read_only=True)

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "parent",
            "total_likes",
            "is_liked",
            "total_replies",
            "created_at",
        ]

    def get_is_liked(self, obj):
        user = self.context["request"].user
        return user.is_authenticated and obj.comment_likes.filter(user=user).exists()


# ---------------------------
# POST SERIALIZER (SHOW TAGS)
# ---------------------------
class PostSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    total_likes = serializers.IntegerField(read_only=True)
    total_comments = serializers.IntegerField(source="total_comments_count", read_only=True)
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

    def create(self, validated_data):
        request = self.context["request"]
        author = request.user
        
        validated_data["author"] = author
        
        tag_ids = validated_data.pop("tags", [])
        image = validated_data.pop("image", None)

        # 1) Create post WITHOUT image — safe generate PK
        post = Post.objects.create(**validated_data)

        # 2) Attach image afterwards
        if image:
            post.image = image
            post.save()   # <-- triggers update, NOT insert

        # 3) Set tags
        if tag_ids:
            post.tags.set(tag_ids)

        return post

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop("tags", None)
        post = super().update(instance, validated_data)
        
        if "image" in validated_data and validated_data["image"] is None:
            if post.image:
                post.image.delete(save=False)

        if tag_ids is not None:
            post.tags.set(tag_ids)
        return post
    
    def validate_title(self, value):
        if value and len(value) > 200:
            raise serializers.ValidationError("Title cannot exceed 200 characters.")
        return value

    def validate_content(self, value):
        if len(value) > 8000:
            raise serializers.ValidationError("Content cannot exceed 8000 characters.")
        return value
    
    def validate_tags(self, value):
        if not value:
            return []

        if len(value) > 5:
            raise serializers.ValidationError("You can select a maximum of 5 tags.")

        valid_ids = list(Tag.objects.filter(id__in=value).values_list("id", flat=True))
        if len(valid_ids) != len(set(value)):
            raise serializers.ValidationError("Invalid tag IDs provided.")

        return value

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
            raise serializers.ValidationError("Content cannot be empty.")

        parent = self.initial_data.get("parent")

        if parent:
            if len(value) > 500:
                raise serializers.ValidationError("Replies cannot exceed 500 characters.")
        else:
            # Comment (top level)
            if len(value) > 1000:
                raise serializers.ValidationError("Comments cannot exceed 1000 characters.")

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


# ---------------------------
# Post Search Serializer
# ---------------------------
class PostSearchSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)

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
