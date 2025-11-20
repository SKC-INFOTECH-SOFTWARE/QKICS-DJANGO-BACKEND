from django.urls import path
from .views import (
    PostListCreateView,
    PostDetailView,
    CommentCreateView,
    LikeToggleView
)

urlpatterns = [
    path("posts/", PostListCreateView.as_view(), name="post-list-create"),
    path("posts/<int:pk>/", PostDetailView.as_view(), name="post-detail"),
    path("posts/<int:post_id>/comments/", CommentCreateView.as_view(), name="comment-create"),
    path("posts/<int:post_id>/like/", LikeToggleView.as_view(), name="like-post"),
    path("comments/<int:comment_id>/like/", LikeToggleView.as_view(), name="like-comment"),
]