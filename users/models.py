from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


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
