from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
import uuid
from django.conf import settings
from django.core.files.storage import default_storage


class User(AbstractUser):

    USER_TYPES = [
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("expert", "Expert"),
        ("entrepreneur", "Entrepreneur"),
        ("investor", "Investor"),
        ("normal", "Normal User"),
    ]

    STATUS_TYPES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("banned", "Banned"),
    ]

    uuid = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )
    # USER ROLE
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="normal")

    # ACCOUNT STATUS
    status = models.CharField(max_length=20, choices=STATUS_TYPES, default="active")

    # OPTIONAL PHONE NUMBER
    phone = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9]{7,15}$",
                message="Phone number must contain only digits (7–15 digits).",
            )
        ],
    )

    # OPTIONAL BASIC PROFILE PICTURE
    profile_picture = models.ImageField(
        upload_to="users/profile_pics/", blank=True, null=True
    )

    # TIMESTAMPS
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} ({self.user_type})"

    def save(self, *args, **kwargs):
        # Get the previous record (if exists)
        try:
            old = User.objects.get(pk=self.pk)
            old_image = old.profile_picture
        except User.DoesNotExist:
            old = None
            old_image = None

        # CASE 1 — User REMOVED the picture
        if not self.profile_picture:
            if old_image and default_storage.exists(old_image.path):
                default_storage.delete(old_image.path)
            return super().save(*args, **kwargs)

        # CASE 2 — User did NOT upload a new picture → DO NOTHING
        if old_image and self.profile_picture == old_image:
            return super().save(*args, **kwargs)

        # CASE 3 — New image uploaded, delete old one
        if old_image and default_storage.exists(old_image.path):
            default_storage.delete(old_image.path)

        # COMPRESS NEW IMAGE
        img = Image.open(self.profile_picture)

        if img.mode != "RGB":
            img = img.convert("RGB")

        buffer = BytesIO()
        quality = 85

        while True:
            buffer.seek(0)
            buffer.truncate()
            img.save(buffer, format="JPEG", quality=quality)
            size_kb = buffer.tell() / 1024
            if size_kb <= 200 or quality <= 40:
                break
            quality -= 5

        # Use USER ID (BEST) or username
        filename = f"user_{self.pk or 'new'}.jpg"

        self.profile_picture = ContentFile(buffer.getvalue(), name=filename)

        super().save(*args, **kwargs)
