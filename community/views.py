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
    PostSearchSerializer,
    ReplySerializer,
)
from django.contrib.auth import get_user_model
from django.db.models import Q

from rest_framework.generics import ListAPIView
from django.db.models import Count
from .pagination import (
    PostCursorPagination,
    CommentCursorPagination,
    ReplyCursorPagination,
)
from datetime import datetime, timedelta
from django.utils import timezone

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
class PostByTagView(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination

    def get_queryset(self):
        tag = get_object_or_404(Tag, slug=self.kwargs["slug"])
        return (
            Post.objects.filter(tags=tag)
            .select_related("author")
            .prefetch_related("tags", "post_likes")
            .annotate(total_comments_count=Count("comments"))
            .order_by("-created_at")
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
class PostListCreateView(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination
    
    def get_permissions(self):
            if self.request.method == "POST":
                return [IsAuthenticated()]
            return [IsAuthenticatedOrReadOnly()]
        
    def get_queryset(self):
        return (
            Post.objects.select_related("author")
            .prefetch_related("tags", "post_likes")
            .annotate(total_comments_count=Count("comments"))
            .order_by("-created_at")
        )

    def post(self, request, *args, **kwargs):
        now = timezone.localtime()
        today = now.date()

        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_of_day = start_of_day + timedelta(days=1)

        post_count_today = Post.objects.filter(
            author_id=request.user.id,
            created_at__gte=start_of_day,
            created_at__lt=end_of_day
        ).count()
        
        if post_count_today >= 10:
            return Response(
                {"error": "Daily post limit reached (10 per day)."},
                status=429
            )

        serializer = PostCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        post = serializer.save()

        return Response(
            PostSerializer(post, context={"request": request}).data,
            status=201
        )


# ---------------------------
# POST BY USERNAME
# ---------------------------
class PostByUserView(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = PostSerializer
    pagination_class = PostCursorPagination

    def get_queryset(self):
        user = get_object_or_404(User, username=self.kwargs["username"])
        return (
            Post.objects.filter(author=user)
            .select_related("author")
            .prefetch_related("tags", "post_likes")
            .annotate(total_comments_count=Count("comments"))
            .order_by("-created_at")
        )


# ---------------------------
# SINGLE POST VIEW
# ---------------------------
class PostDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(
            Post.objects.select_related("author")
            .prefetch_related("tags", "post_likes")
            .annotate(total_comments_count=Count("comments")),
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
class CommentListCreateView(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = CommentSerializer
    pagination_class = CommentCursorPagination

    def get_queryset(self):
        post = get_object_or_404(Post, id=self.kwargs["post_id"])
        return (
            Comment.objects.filter(post=post, parent__isnull=True)
            .select_related("author")
            .prefetch_related("comment_likes")
            .order_by("-created_at")
        )

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)
        today = timezone.now().date()
        comment_count_today = Comment.objects.filter(
            author=request.user, created_at__date=today
        ).count()

        if comment_count_today >= 100:
            return Response(
                {"error": "Daily comment+reply limit reached (100 per day)."},
                status=429,
            )
        serializer = CommentCreateSerializer(
            data=request.data, context={"request": request, "post": post}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

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
from .pagination import ReplyCursorPagination
from rest_framework.generics import ListAPIView


class ReplyListCreateView(ListAPIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = ReplySerializer
    pagination_class = ReplyCursorPagination

    def get_queryset(self):
        parent = get_object_or_404(Comment, id=self.kwargs["comment_id"])
        return (
            parent.replies.select_related("author")
            .prefetch_related("comment_likes")
            .order_by("created_at")
        )

    def post(self, request, comment_id):
        parent = get_object_or_404(Comment, id=comment_id)
        today = timezone.now().date()
        comment_count_today = Comment.objects.filter(
            author=request.user, created_at__date=today
        ).count()

        if comment_count_today >= 100:
            return Response(
                {"error": "Daily comment+reply limit reached (100 per day)."},
                status=429,
            )

        if parent.parent is not None:
            return Response({"error": "Cannot reply to a reply"}, status=400)

        serializer = CommentCreateSerializer(
            data=request.data,
            context={"request": request, "post": parent.post},
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        reply = Comment.objects.create(
            post=parent.post,
            author=request.user,
            content=serializer.validated_data["content"],
            parent=parent,
        )

        return Response(
            ReplySerializer(reply, context={"request": request}).data, status=201
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
            return Response(ReplySerializer(reply, context={"request": request}).data)
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

        # Load Target + like_qs first
        if post_id:
            target = get_object_or_404(Post, id=post_id)
            like_qs = Like.objects.filter(user=user, post=target)
            serializer_class = PostSerializer

        elif comment_id:
            target = get_object_or_404(Comment, id=comment_id)
            like_qs = Like.objects.filter(user=user, comment=target)

            if target.parent:
                serializer_class = ReplySerializer
            else:
                serializer_class = CommentSerializer

        else:
            return Response({"error": "Invalid request"}, status=400)

        # NOW perform rate limit check BEFORE creating LIKE
        if not like_qs.exists():   # user is about to LIKE
            today = timezone.now().date()
            like_count_today = Like.objects.filter(
                user=user,
                created_at__date=today
            ).count()

            if like_count_today >= 1000:
                return Response(
                    {"error": "Daily like limit reached (1000 per day)."},
                    status=429
                )

        # LIKE TOGGLE
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
            {"status": action, "data": serializer_class(target, context={"request": request}).data}
        )



# ---------------------------
# SEARCH POSTS
# ---------------------------
class SearchPostsView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = PostCursorPagination
    
    def get(self, request):
        query = request.GET.get("q", "").strip()

        if not query:
            return Response({"error": "Search query 'q' is required"}, status=400)

        posts = (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .annotate(total_comments_count=Count("comments"))
            .filter(
                Q(title__icontains=query)
                | Q(content__icontains=query)
                | Q(tags__name__icontains=query)
            )
            .distinct()
            .order_by("-created_at")
        )

        serializer = PostSearchSerializer(
            posts, many=True, context={"request": request}
        )
        return Response(serializer.data)
