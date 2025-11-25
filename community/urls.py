from django.urls import path
from .views import (
    PostListCreateView,
    PostByUserView,
    PostDetailView,

    CommentListCreateView,
    CommentDetailView,

    ReplyListCreateView,
    ReplyDetailView,

    LikeToggleView,
)

urlpatterns = [
    # POSTS
    path("posts/", PostListCreateView.as_view(), name="post-list-create"),
    path("posts/user/<str:username>/", PostByUserView.as_view(), name="post-by-user"),
    path("posts/<int:pk>/", PostDetailView.as_view(), name="post-detail"),

    # COMMENTS
    path("posts/<int:post_id>/comments/", CommentListCreateView.as_view(), name="comment-list-create"),
    path("comments/<int:comment_id>/", CommentDetailView.as_view(), name="comment-detail"),

    # REPLIES
    path("comments/<int:comment_id>/replies/", ReplyListCreateView.as_view(), name="reply-list-create"),
    path("replies/<int:reply_id>/", ReplyDetailView.as_view(), name="reply-detail"),

    # LIKES
    path("posts/<int:post_id>/like/", LikeToggleView.as_view(), name="like-post"),
    path("comments/<int:comment_id>/like/", LikeToggleView.as_view(), name="like-comment"),
]
