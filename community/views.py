from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.db import transaction
from .models import Post, Comment, Like
from .serializers import (
    PostSerializer, PostCreateSerializer,
    CommentCreateSerializer, CommentSerializer
)
from users.permissions import IsAdmin

class PostListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        posts = Post.objects.select_related("author").prefetch_related(
            "post_likes",
            "top_level_comments__author",
            "top_level_comments__replies__author",
            "top_level_comments__comment_likes",
            "top_level_comments__replies__comment_likes",
        )
        serializer = PostSerializer(posts, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = PostCreateSerializer(data=request.data)
        if serializer.is_valid():
            post = serializer.save(author=request.user)
            return Response(PostSerializer(post, context={"request": request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PostDetailView(APIView):
    permission_classes = [AllowAny]

    def get_object(self, pk):
        return get_object_or_404(
            Post.objects.select_related("author").prefetch_related(
                "post_likes",
                "top_level_comments__author",
                "top_level_comments__replies__author",
                "top_level_comments__comment_likes",
                "top_level_comments__replies__comment_likes",
            ),
            pk=pk
        )

    def get(self, request, pk):
        post = self.get_object(pk)
        return Response(PostSerializer(post, context={"request": request}).data)

    def patch(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"error": "Login required"}, status=status.HTTP_401_UNAUTHORIZED)
        post = self.get_object(pk)
        if post.author != request.user:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        serializer = PostCreateSerializer(post, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(PostSerializer(post, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_authenticated:
            return Response({"error": "Login required"}, status=status.HTTP_401_UNAUTHORIZED)
        post = self.get_object(pk)
        if post.author != request.user and request.user.user_type not in ["admin", "superadmin"]:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id):
        post = get_object_or_404(Post, id=post_id)

        # Use serializer for full validation (content required, stripped, etc.)
        serializer = CommentCreateSerializer(
            data=request.data,
            context={"request": request, "post": post}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        parent = serializer.validated_data.get("parent")

        # Final parent validation: must be top-level comment on same post
        if parent:
            if parent.post != post or parent.parent is not None:
                return Response({
                    "error": "Invalid parent comment"
                }, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            comment = Comment.objects.create(
                post=post,
                author=request.user,
                content=serializer.validated_data["content"].strip(),
                parent=parent
            )

            return Response(
                CommentSerializer(comment, context={"request": request}).data,
                status=status.HTTP_201_CREATED
            )


class LikeToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, post_id=None, comment_id=None):
        user = request.user

        if post_id and comment_id:
            return Response({"error": "Cannot like both"}, status=status.HTTP_400_BAD_REQUEST)

        if post_id:
            target = get_object_or_404(Post, id=post_id)
            like_qs = Like.objects.filter(user=user, post=target, comment=None)
            target_type = "post"
        elif comment_id:
            target = get_object_or_404(Comment, id=comment_id)
            like_qs = Like.objects.filter(user=user, comment=target, post=None)
            target_type = "comment"
        else:
            return Response({"error": "post_id or comment_id required"}, status=status.HTTP_400_BAD_REQUEST)

        if like_qs.exists():
            like_qs.delete()
            action = "unliked"
        else:
            Like.objects.create(user=user, post=target if post_id else None, comment=target if comment_id else None)
            action = "liked"

        serializer = PostSerializer(target, context={"request": request}) if target_type == "post" else CommentSerializer(target, context={"request": request})

        return Response({
            "status": action,
            "data": serializer.data
        })