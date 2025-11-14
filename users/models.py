from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    # ROLES
    USER_TYPES = (
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("expert", "Expert"),
        ("startup", "Startup"),
        ("investor", "Investor"),
        ("guest", "Guest"),
    )
    # STATUS
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
    )

    # Fields
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="guest")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    is_verified = models.BooleanField(default=False)
    phone = models.CharField(max_length=15, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Prevent login if suspended
    def is_active_user(self):
        return self.is_active and self.status == "active"

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()} | {self.get_status_display()})"
