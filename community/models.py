from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.core.files.storage import default_storage
import uuid
import mimetypes
from PIL import Image

User = get_user_model()


# ---------------------------
# TAG MODEL
# ---------------------------
class Tag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:90]
            slug = base
            counter = 1
            while Tag.objects.filter(slug=slug).exists():
                counter += 1
                slug = f"{base}-{counter}"
            self.slug = slug
        super().save(*args, **kwargs)


def get_or_create_tags(names, *, limit=5):
    """Resolve a list of tag *names* to Tag rows, creating the ones that don't
    exist yet — but only ever called at post save time.

    Tags used to be created the moment a user typed one while composing (a live
    POST /tags/), so abandoned drafts littered the table with unused tags. Now
    the compose UI just collects names and the tag row is born here, when the
    post is actually saved. Matching is case-insensitive so "React"/"react"
    reuse one row; blanks/dupes are dropped and the count is capped at `limit`.
    """
    resolved = []
    seen = set()
    for raw in names or []:
        name = (raw or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        tag = Tag.objects.filter(name__iexact=name).first()
        if tag is None:
            tag = Tag.objects.create(name=name[:80])
        resolved.append(tag)
        if len(resolved) >= limit:
            break
    return resolved


def prune_orphan_tags(tag_ids):
    """Delete any tag among `tag_ids` that is no longer attached to a post.

    Deleting a post, or editing a post so a tag is de-selected, leaves the Tag
    row behind (M2M rows go, the Tag stays). Those orphans pile up in the tag
    picker and the "trending" list forever. Call this with the ids that were
    just detached and it removes only the ones that now belong to zero posts —
    a tag still used by another post is never touched (the `posts__isnull=True`
    guard). Returns how many were deleted. Safe to call with an empty/None list.
    """
    if not tag_ids:
        return 0
    orphans = Tag.objects.filter(id__in=list(tag_ids), posts__isnull=True)
    deleted, _ = orphans.delete()
    return deleted


# ---------------------------
# POST MODEL
# ---------------------------
class Post(models.Model):
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="community_posts"
    )
    title = models.CharField(max_length=300, blank=True, null=True)

    # TEMPORARY (to be removed later)
    content = models.TextField(max_length=10000)

    # ✅ NEW FIELDS FOR SUBSCRIPTION LOGIC
    preview_content = models.TextField(
        max_length=500,
        blank=True,
        help_text="Visible to all users (non-premium)",
    )
    full_content = models.TextField(
        max_length=10000,
        blank=True,
        help_text="Visible only to premium users",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    knowledge_hub = models.BooleanField(
        default=False,
        help_text="True = Knowledge Hub post (Idea/Structured knowledge post)",
        db_index=True,
    )

    # ---- Moderation (admin) ----
    is_hidden = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Hidden from the public feed by a moderator (soft removal).",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_posts",
        help_text="Admin who hid this post.",
    )
    moderation_reason = models.CharField(max_length=300, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["knowledge_hub"]),
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["is_hidden", "created_at"]),
        ]

    def __str__(self):
        return f"{self.author.username} - {self.title or 'Post'} ({self.id})"

    @property
    def total_likes(self):
        return self.post_likes.count()

    @property
    def total_comments(self):
        return self.comments.count()

    def top_level_comments(self):
        return self.comments.filter(parent__isnull=True)


# ---------------------------
# COMMENT MODEL
# ---------------------------
class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="community_comments"
    )

    # TEMPORARY
    content = models.TextField(max_length=5000)

    # ✅ NEW FIELDS
    preview_content = models.TextField(
        max_length=300,
        blank=True,
        help_text="Visible to all users",
    )
    full_content = models.TextField(
        max_length=5000,
        blank=True,
        help_text="Visible only to premium users",
    )

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="replies",
        help_text="Null = top-level comment, Not null = reply",
    )

    # ---- Moderation (admin) ----
    is_hidden = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Hidden from the public feed by a moderator (soft removal).",
    )
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_comments",
        help_text="Admin who hid this comment.",
    )
    moderation_reason = models.CharField(max_length=300, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post", "created_at"]),
            models.Index(fields=["parent"]),
            models.Index(fields=["is_hidden"]),
        ]

    def __str__(self):
        return f"Comment by {self.author} on Post {self.post.id}"

    @property
    def total_likes(self):
        return self.comment_likes.count()

    @property
    def depth(self):
        return 1 if self.parent else 0

    def clean(self):
        if self.parent and self.parent.parent:
            raise ValidationError(
                "Replies to replies are not allowed. Only one level of reply is supported."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


# ---------------------------
# LIKE MODEL (UNCHANGED)
# ---------------------------
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


# ====================================
# POST MEDIA MODEL
# ====================================


def post_media_upload_path(instance, filename):
    ext = filename.split(".")[-1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    return f"community/post_media/{unique_name}"


class PostMedia(models.Model):
    IMAGE = "image"
    VIDEO = "video"

    MEDIA_TYPE_CHOICES = [
        (IMAGE, "Image"),
        (VIDEO, "Video"),
    ]

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="media",
        db_index=True,
    )

    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPE_CHOICES,
        editable=False,
    )

    file = models.FileField(upload_to=post_media_upload_path)

    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["post", "order"], name="unique_post_media_order"
            )
        ]

    def __str__(self):
        return f"{self.media_type} for Post {self.post.id}"

    def clean(self):
        if not self.file:
            raise ValidationError("File is required.")

        # File size validation (50MB)
        max_size = 50 * 1024 * 1024
        if self.file.size > max_size:
            raise ValidationError("File size exceeds 50MB limit.")

        mime_type, _ = mimetypes.guess_type(self.file.name)

        if not mime_type:
            raise ValidationError("Could not determine file type.")

        # IMAGE VALIDATION
        if mime_type.startswith("image"):
            try:
                self.file.seek(0)
                img = Image.open(self.file)
                img.verify()
                self.file.seek(0)
                self.media_type = self.IMAGE
            except (OSError, SyntaxError, ValueError):
                raise ValidationError("Invalid image file.")
        # VIDEO VALIDATION
        elif mime_type.startswith("video"):
            allowed_video_types = [
                "video/mp4",
                "video/quicktime",
                "video/x-msvideo",
            ]

            if mime_type not in allowed_video_types:
                raise ValidationError("Unsupported video format.")

            self.media_type = self.VIDEO

        else:
            raise ValidationError("Only image and video files are allowed.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)
