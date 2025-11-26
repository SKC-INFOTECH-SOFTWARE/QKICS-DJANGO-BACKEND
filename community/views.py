from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny,
    IsAuthenticatedOrReadOnly,
)
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Post, Comment, Like, Tag
from .serializers import (
    PostSerializer,
    PostCreateSerializer,
    CommentCreateSerializer,
    CommentSerializer,
    TagSerializer,
)
from django.contrib.auth import get_user_model

User = get_user_model()


# ---------------------------
# TAG LIST + CREATE (Admin Only for Create)
# ---------------------------
class TagListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        tags = Tag.objects.all().order_by("name")
        return Response(TagSerializer(tags, many=True).data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        if request.user.user_type not in ["admin", "superadmin"]:
            return Response({"error": "Only admins can create tags"}, status=403)

        serializer = TagSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


# ---------------------------
# FILTER POSTS BY TAG
# ---------------------------
class PostByTagView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, slug):
        tag = get_object_or_404(Tag, slug=slug)
        posts = (
            Post.objects.filter(tags=tag)
            .select_related("author")
            .prefetch_related(
                "post_likes",
                "comments__author",
                "comments__replies__author",
                "comments__comment_likes",
                "comments__replies__comment_likes",
            )
        )
        return Response(
            PostSerializer(posts, many=True, context={"request": request}).data
        )


# ---------------------------
# TAG UPDATE & DELETE (Admin Only)
# ---------------------------
class TagDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, id):
        return get_object_or_404(Tag, id=id)

    def put(self, request, id):
        if request.user.user_type not in ["admin", "superadmin"]:
            return Response({"error": "Only admins can update tags"}, status=403)

        tag = self.get_object(id)
        serializer = TagSerializer(tag, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=400)

    def delete(self, request, id):
        if request.user.user_type not in ["admin", "superadmin"]:
            return Response({"error": "Only admins can delete tags"}, status=403)

        tag = self.get_object(id)
        tag.delete()
        return Response(status=204)


# ---------------------------
# POST LIST + CREATE
# ---------------------------
class PostListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        posts = Post.objects.select_related("author").prefetch_related(
            "post_likes",
            "comments__author",
            "comments__replies__author",
            "comments__comment_likes",
            "comments__replies__comment_likes",
            "tags",
        )
        serializer = PostSerializer(posts, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=401)

        serializer = PostCreateSerializer(data=request.data)
        if serializer.is_valid():
            post = serializer.save(author=request.user)
            return Response(
                PostSerializer(post, context={"request": request}).data, status=201
            )
        return Response(serializer.errors, status=400)


# ---------------------------
# POST BY USERNAME
# ---------------------------
class PostByUserView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        posts = (
            Post.objects.filter(author=user)
            .select_related("author")
            .prefetch_related(
                "post_likes",
                "comments__author",
                "comments__replies__author",
                "comments__comment_likes",
                "comments__replies__comment_likes",
                "tags",
            )
        )
        serializer = PostSerializer(posts, many=True, context={"request": request})
        return Response(serializer.data)


# ---------------------------
# SINGLE POST VIEW
# ---------------------------
class PostDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(
            Post.objects.select_related("author").prefetch_related(
                "post_likes",
                "comments__author",
                "comments__replies__author",
                "comments__comment_likes",
                "comments__replies__comment_likes",
                "tags",
            ),
            pk=pk,
        )

    def get(self, request, pk):
        post = self.get_object(pk)
        return Response(PostSerializer(post, context={"request": request}).data)

    def put(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"error": "Login required"}, status=401)

        post = self.get_object(pk)
        if post.author != request.user:
            return Response({"error": "Not authorized"}, status=403)

        serializer = PostCreateSerializer(post, data=request.data, partial=False)
        if serializer.is_valid():
            serializer.save()
            return Response(PostSerializer(post, context={"request": request}).data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"error": "Login required"}, status=401)

        post = self.get_object(pk)
        if post.author != request.user:
            return Response({"error": "Not authorized"}, status=403)

        post.delete()
        return Response(status=204)


# ---------------------------
# COMMENT LIST + CREATE
# ---------------------------
class CommentListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        comments = (
            post.comments.filter(parent__isnull=True)
            .select_related("author")
            .prefetch_related(
                "replies__author",
                "comment_likes",
                "replies__comment_likes",
            )
        )
        serializer = CommentSerializer(
            comments, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        serializer = CommentCreateSerializer(
            data=request.data, context={"request": request, "post": post}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        parent = serializer.validated_data.get("parent")

        if parent:
            if parent.post != post or parent.parent is not None:
                return Response({"error": "Invalid parent comment"}, status=400)

        with transaction.atomic():
            comment = serializer.save()
            return Response(
                CommentSerializer(comment, context={"request": request}).data,
                status=201,
            )


# ---------------------------
# COMMENT UPDATE / DELETE
# ---------------------------
class CommentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        if comment.author != request.user:
            return Response({"error": "Not authorized"}, status=403)

        serializer = CommentCreateSerializer(comment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                CommentSerializer(comment, context={"request": request}).data
            )
        return Response(serializer.errors, status=400)

    def delete(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        if comment.author != request.user:
            return Response({"error": "Not authorized"}, status=403)

        comment.delete()
        return Response(status=204)


# ---------------------------
# REPLY LIST + CREATE
# ---------------------------
class ReplyListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, comment_id):
        comment = get_object_or_404(Comment, id=comment_id)
        replies = comment.replies.select_related("author").prefetch_related(
            "comment_likes"
        )
        serializer = CommentSerializer(replies, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request, comment_id):
        parent = get_object_or_404(Comment, id=comment_id)
        if parent.parent is not None:
            return Response({"error": "Cannot reply to a reply"}, status=400)

        serializer = CommentCreateSerializer(
            data=request.data,
            context={"request": request, "post": parent.post},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        with transaction.atomic():
            reply = Comment.objects.create(
                post=parent.post,
                author=request.user,
                content=serializer.validated_data["content"],
                parent=parent,
            )
            return Response(
                CommentSerializer(reply, context={"request": request}).data, status=201
            )


# ---------------------------
# REPLY UPDATE / DELETE
# ---------------------------
class ReplyDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, reply_id):
        reply = get_object_or_404(Comment, id=reply_id)
        if reply.parent is None:
            return Response({"error": "Not a reply"}, status=400)
        if reply.author != request.user:
            return Response({"error": "Not authorized"}, status=403)

        serializer = CommentCreateSerializer(reply, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(CommentSerializer(reply, context={"request": request}).data)
        return Response(serializer.errors, status=400)

    def delete(self, request, reply_id):
        reply = get_object_or_404(Comment, id=reply_id)
        if reply.parent is None:
            return Response({"error": "Not a reply"}, status=400)
        if reply.author != request.user:
            return Response({"error": "Not authorized"}, status=403)

        reply.delete()
        return Response(status=204)


# ---------------------------
# LIKE TOGGLE
# ---------------------------
class LikeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id=None, comment_id=None):
        user = request.user

        if post_id:
            target = get_object_or_404(Post, id=post_id)
            like_qs = Like.objects.filter(user=user, post=target)
            serializer_class = PostSerializer

        elif comment_id:
            target = get_object_or_404(Comment, id=comment_id)
            like_qs = Like.objects.filter(user=user, comment=target)
            serializer_class = CommentSerializer

        else:
            return Response({"error": "Invalid request"}, status=400)

        if like_qs.exists():
            like_qs.delete()
            action = "unliked"
        else:
            Like.objects.create(
                user=user,
                post=target if post_id else None,
                comment=target if comment_id else None,
            )
            action = "liked"

        return Response(
            {
                "status": action,
                "data": serializer_class(target, context={"request": request}).data,
            }
        )
