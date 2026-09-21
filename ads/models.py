from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
from PIL import Image

User = get_user_model()


def ad_media_upload_path(instance, filename):
    ext = filename.split(".")[-1].lower()
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    return f"ads/media/{unique_name}"


class Advertisement(models.Model):

    IMAGE = "image"
    VIDEO = "video"

    MEDIA_TYPE_CHOICES = [
        (IMAGE, "Image"),
        (VIDEO, "Video"),
    ]

    PLACEMENT_CHOICES = [
        ("sidebar_featured", "Sidebar Featured Partner"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Basic Info
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Media
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_TYPE_CHOICES,
        editable=False,
    )

    file = models.FileField(upload_to=ad_media_upload_path)

    # CTA
    redirect_url = models.URLField()
    button_text = models.CharField(
        max_length=50,
        default="Learn More",
    )

    # Placement
    placement = models.CharField(
        max_length=50,
        choices=PLACEMENT_CHOICES,
        default="sidebar_featured",
        db_index=True,
    )

    # Scheduling
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    is_active = models.BooleanField(default=True, db_index=True)

    # Admin Tracking
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ads_created",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["placement", "is_active"]),
            models.Index(fields=["start_datetime", "end_datetime"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.media_type})"

    # Video is validated by extension (we can't cheaply sniff container formats);
    # images are validated by actually opening them with Pillow, so formats that
    # ``mimetypes`` doesn't know on the prod image (webp/jfif on py3.11) still work.
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "avi"}

    # The in-feed card clamps the description to a couple of lines with a
    # "See more" toggle, so cap it at 100 words to keep cards scannable.
    DESCRIPTION_MAX_WORDS = 100

    def clean(self):
        if not self.file:
            raise ValidationError("File is required.")

        word_count = len((self.description or "").split())
        if word_count > self.DESCRIPTION_MAX_WORDS:
            raise ValidationError(
                {
                    "description": (
                        f"Description must be at most {self.DESCRIPTION_MAX_WORDS} words "
                        f"(currently {word_count})."
                    )
                }
            )

        # Max file size: 50MB
        max_size = 50 * 1024 * 1024
        if self.file.size > max_size:
            raise ValidationError("File size exceeds 50MB limit.")

        ext = self.file.name.rsplit(".", 1)[-1].lower() if "." in self.file.name else ""
        content_type = getattr(getattr(self.file, "file", None), "content_type", "") or ""

        if ext in self.ALLOWED_VIDEO_EXTENSIONS or content_type.startswith("video/"):
            if ext not in self.ALLOWED_VIDEO_EXTENSIONS:
                raise ValidationError(
                    "Unsupported video format. Allowed: "
                    + ", ".join(sorted(self.ALLOWED_VIDEO_EXTENSIONS))
                    + "."
                )
            self.media_type = self.VIDEO
        else:
            # IMAGE VALIDATION — let Pillow decide whether it's a real image
            try:
                self.file.seek(0)
                img = Image.open(self.file)
                img.verify()
                self.file.seek(0)
                self.media_type = self.IMAGE
            except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
                raise ValidationError(
                    "Only image (jpg, png, gif, webp) and video (mp4, webm, mov, avi) "
                    "files are allowed."
                )

        # Date validation
        if self.start_datetime and self.end_datetime and self.start_datetime >= self.end_datetime:
            raise ValidationError("End datetime must be after start datetime.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.file:
            self.file.delete(save=False)
        super().delete(*args, **kwargs)

    @property
    def is_currently_running(self):
        now = timezone.now()
        return (
            self.is_active
            and self.start_datetime <= now <= self.end_datetime
        )