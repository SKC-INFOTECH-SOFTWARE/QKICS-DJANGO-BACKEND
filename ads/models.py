from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
import uuid
import mimetypes
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

    def clean(self):
        if not self.file:
            raise ValidationError("File is required.")

        # Max file size: 50MB
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
                "video/webm",
                "video/quicktime",
                "video/x-msvideo",
            ]

            if mime_type not in allowed_video_types:
                raise ValidationError("Unsupported video format.")

            self.media_type = self.VIDEO

        else:
            raise ValidationError("Only image and video files are allowed.")

        # Date validation
        if self.start_datetime >= self.end_datetime:
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