from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from PIL import Image, ImageOps
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
User = get_user_model()


# ---------------------------
# TAG MODEL (ADMIN CONTROLLED)
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


# ---------------------------
# POST MODEL
# ---------------------------
class Post(models.Model):
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="community_posts"
    )
    title = models.CharField(max_length=300, blank=True, null=True)
    content = models.TextField(max_length=10000)
    image = models.ImageField(upload_to="community/posts/", blank=True, null=True)

    # NEW — MULTI TAGS
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")

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
        return self.comments.filter(parent__isnull=True)
    
    # IMAGE HANDLING
    def delete(self, *args, **kwargs):
        if self.image and self.image.name:
            if default_storage.exists(self.image.path):
                default_storage.delete(self.image.path)
        super().delete(*args, **kwargs)
        
    def save(self, *args, **kwargs):
        # Get old version before saving
        try:
            old = Post.objects.get(pk=self.pk)
            old_image = old.image
        except Post.DoesNotExist:
            old = None
            old_image = None

        # CASE 1 — Image removed
        if not self.image:
            if old_image and default_storage.exists(old_image.path):
                default_storage.delete(old_image.path)
            return super().save(*args, **kwargs)

        # CASE 2 — No new image uploaded → do nothing
        if old_image and self.image == old_image:
            return super().save(*args, **kwargs)

        # CASE 3 — New image uploaded → delete old file
        if old_image and default_storage.exists(old_image.path):
            default_storage.delete(old_image.path)

        # FIRST SAVE IF NEW POST (no ID yet)
        is_new = self.pk is None
        if is_new:
            temp = self.image
            self.image = None
            super().save(*args, **kwargs)
            self.image = temp

        # ==== IMAGE PROCESSING ====

        img = Image.open(self.image)

        # Fix rotation using EXIF
        img = ImageOps.exif_transpose(img)

        # Convert to RGB for JPEG
        if img.mode != "RGB":
            img = img.convert("RGB")

        buffer = BytesIO()
        quality = 85

        # Compress until <= 200 KB
        while True:
            buffer.seek(0)
            buffer.truncate()
            img.save(buffer, format="JPEG", quality=quality)
            size_kb = buffer.tell() / 1024

            if size_kb <= 200 or quality <= 40:
                break

            quality -= 5

        # File name based on POST ID
        filename = f"{self.pk}.jpg"

        # Save compressed image
        self.image = ContentFile(buffer.getvalue(), name=filename)

        super().save(*args, **kwargs)


# ---------------------------
# COMMENT MODEL
# ---------------------------
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
# LIKE MODEL
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
