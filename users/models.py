from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    # ────────────────────── USER ROLES ──────────────────────
    USER_TYPES = (
        ("superadmin", "Super Admin"),
        ("admin", "Admin"),
        ("expert", "Expert"),
        ("entrepreneur", "Entrepreneur"),
        ("investor", "Investor"),
        ("normal", "Normal User"),
    )

    # ────────────────────── ACCOUNT STATUS ──────────────────────
    STATUS_CHOICES = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("suspended", "Suspended"),
    )

    # ────────────────────── FIELDS ──────────────────────
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPES,
        default="normal",
        help_text="User role in the platform"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Account status"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="True if admin has verified the user"
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="10-digit Indian mobile number"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Account creation time (IST)"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last update time (IST)"
    )

    # ────────────────────── METHODS ──────────────────────
    def is_active_user(self):
        """Allow login only if Django active + status active"""
        return self.is_active and self.status == "active"

    def __str__(self):
        verified = "✓" if self.is_verified else "⏳"
        return f"{self.username} ({self.get_user_type_display()} | {self.get_status_display()}) {verified}"

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]