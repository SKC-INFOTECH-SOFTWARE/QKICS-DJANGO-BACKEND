from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()


class Post(models.Model):
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="community_posts"
    )
    title = models.CharField(max_length=300, blank=True, null=True)
    content = models.TextField(max_length=10000)
    image = models.ImageField(upload_to="community/posts/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author.username} - {self.title or 'Post'} ({self.id})"

    @property
    def total_likes(self):
        return self.post_likes.count()

    @property
    def total_comments(self):
        return self.comments.count()

    def top_level_comments(self):
        """Used by PostSerializer to show only top-level comments + their replies"""
        return self.comments.filter(parent__isnull=True)


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="community_comments"
    )
    content = models.TextField(max_length=5000)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        help_text="Null = top-level comment, Not null = reply to a top-level comment",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self):
        return f"Comment by {self.author} on Post {self.post.id}"

    @property
    def total_likes(self):
        return self.comment_likes.count()

    @property
    def depth(self):
        """Facebook-style: 0 = top-level, 1 = reply"""
        return 1 if self.parent else 0

    def clean(self):
        """Block replies to replies (max 1 level)"""
        if self.parent and self.parent.parent:
            raise ValidationError(
                "Replies to replies are not allowed. Only one level of reply is supported."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Like(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="community_likes"
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, null=True, blank=True, related_name="post_likes"
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comment_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "post"],
                name="unique_user_post_like",
                condition=models.Q(post__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["user", "comment"],
                name="unique_user_comment_like",
                condition=models.Q(comment__isnull=False),
            ),
            models.CheckConstraint(
                check=models.Q(post__isnull=False) | models.Q(comment__isnull=False),
                name="like_must_have_target",
            ),
            models.CheckConstraint(
                check=~models.Q(post__isnull=False, comment__isnull=False),
                name="like_cannot_have_both",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "post"]),
            models.Index(fields=["user", "comment"]),
        ]

    def __str__(self):
        target = self.post or self.comment
        return f"{self.user} likes {target}"
