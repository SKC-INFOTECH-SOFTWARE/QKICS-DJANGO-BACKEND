from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

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

    # USER ROLE
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPES,
        default="normal"
    )

    # ACCOUNT STATUS
    status = models.CharField(
        max_length=20,
        choices=STATUS_TYPES,
        default="active"
    )

    # OPTIONAL PHONE NUMBER
    phone = models.CharField(
        max_length=15,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^[0-9]{7,15}$",
                message="Phone number must contain only digits (7–15 digits)."
            )
        ]
    )

    # OPTIONAL BASIC PROFILE PICTURE
    profile_picture = models.ImageField(
        upload_to="users/profile_pics/",
        blank=True,
        null=True
    )

    # TIMESTAMPS
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} ({self.user_type})"
    
    def save(self, *args, **kwargs):
        # Auto-rename file based on username
        if self.profile_picture:
            ext = self.profile_picture.name.split(".")[-1]
            self.profile_picture.name = f"users/profile_pics/{self.username}.{ext}"

            # Compress image to ~200KB
            img = Image.open(self.profile_picture)

            # Convert to RGB if PNG/others
            if img.mode != "RGB":
                img = img.convert("RGB")

            buffer = BytesIO()
            quality = 85   # Start quality

            # Reduce quality until <200 KB
            while True:
                buffer.seek(0)
                buffer.truncate()
                img.save(buffer, format="JPEG", quality=quality)
                size_kb = buffer.tell() / 1024
                if size_kb <= 200 or quality <= 40:
                    break
                quality -= 5

            self.profile_picture = ContentFile(buffer.getvalue(), name=f"users/profile_pics/{self.username}.jpg")

        super().save(*args, **kwargs)