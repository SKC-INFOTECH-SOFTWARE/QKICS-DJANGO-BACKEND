"""
Community feed post moderation (admin).

Powers the admin "Posts" tab. Lists every community post (including
moderator-hidden ones), lets an admin hide/unhide a post (soft removal from the
public feed) or hard-delete it.

Hiding is a soft action: `Post.is_hidden=True` is filtered out of every public
queryset (`community.views.get_optimized_post_queryset`), but the row and its
comments/likes stay in the DB so the action is reversible.
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, filters, status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend

from community.models import Post, Comment, Like
from community.views import _related_count
from adminpanel.serializers import AdminPostSerializer, AdminCommentSerializer
from adminpanel.pagination import AdminCursorPagination


# =====================================================
# LIST ALL COMMUNITY POSTS (incl. hidden)
# =====================================================


class AdminPostListView(generics.ListAPIView):
    serializer_class = AdminPostSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminCursorPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_hidden", "knowledge_hub"]
    search_fields = ["title", "content", "author__username", "author__email"]

    def get_queryset(self):
        # Counts as correlated subqueries (see community.views._related_count) so
        # a 20-row admin page stays a small constant number of queries.
        return (
            Post.objects.select_related("author", "hidden_by")
            .annotate(
                mod_likes=_related_count(Like, "post"),
                mod_comments=_related_count(Comment, "post"),
            )
            .order_by("-created_at")
        )


# =====================================================
# HIDE / UNHIDE A POST (soft moderation)
# =====================================================


class AdminPostModerateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, id):
        post = get_object_or_404(Post, id=id)

        is_hidden = request.data.get("is_hidden")
        if is_hidden is None:
            return Response(
                {"message": "`is_hidden` (true/false) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # accept bool or the strings "true"/"false"
        if isinstance(is_hidden, str):
            is_hidden = is_hidden.strip().lower() == "true"
        is_hidden = bool(is_hidden)

        if is_hidden:
            post.is_hidden = True
            post.hidden_at = timezone.now()
            post.hidden_by = request.user
            post.moderation_reason = (request.data.get("reason") or "")[:300]
        else:
            post.is_hidden = False
            post.hidden_at = None
            post.hidden_by = None
            post.moderation_reason = ""

        post.save(
            update_fields=[
                "is_hidden",
                "hidden_at",
                "hidden_by",
                "moderation_reason",
                "updated_at",
            ]
        )
        return Response(AdminPostSerializer(post).data, status=status.HTTP_200_OK)


# =====================================================
# DELETE A POST (hard delete, cascades comments/likes/media)
# =====================================================


class AdminPostDeleteView(generics.DestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = AdminPostSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"


# =====================================================
# COMMENT MODERATION
# =====================================================


class AdminCommentListView(generics.ListAPIView):
    """All comments/replies (incl. hidden). Filter by `post` to load a single
    post's thread in the admin post modal."""

    serializer_class = AdminCommentSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminCursorPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["is_hidden", "post", "parent"]
    search_fields = ["content", "author__username", "author__email"]

    def get_queryset(self):
        return (
            Comment.objects.select_related("author", "hidden_by")
            .annotate(mod_likes=_related_count(Like, "comment"))
            .order_by("created_at")
        )


class AdminCommentModerateView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, id):
        comment = get_object_or_404(Comment, id=id)

        is_hidden = request.data.get("is_hidden")
        if is_hidden is None:
            return Response(
                {"message": "`is_hidden` (true/false) is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if isinstance(is_hidden, str):
            is_hidden = is_hidden.strip().lower() == "true"
        is_hidden = bool(is_hidden)

        if is_hidden:
            comment.is_hidden = True
            comment.hidden_at = timezone.now()
            comment.hidden_by = request.user
            comment.moderation_reason = (request.data.get("reason") or "")[:300]
        else:
            comment.is_hidden = False
            comment.hidden_at = None
            comment.hidden_by = None
            comment.moderation_reason = ""

        comment.save(
            update_fields=[
                "is_hidden",
                "hidden_at",
                "hidden_by",
                "moderation_reason",
                "updated_at",
            ]
        )
        return Response(AdminCommentSerializer(comment).data, status=status.HTTP_200_OK)


class AdminCommentDeleteView(generics.DestroyAPIView):
    queryset = Comment.objects.all()
    serializer_class = AdminCommentSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"
