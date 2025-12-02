from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================
# Normalized Reference Tables
# ============================
class Industry(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Industries"

    def __str__(self):
        return self.name


class StartupStage(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Startup Stage"
        verbose_name_plural = "Startup Stages"

    def __str__(self):
        return self.name


# ============================
# Main Investor Model
# ============================
class Investor(models.Model):
    INVESTOR_TYPE_CHOICES = [
        ("angel", "Angel Investor"),
        ("vc", "VC Firm"),
        ("fund", "Investment Fund"),
        ("family_office", "Family Office"),
    ]

    APPLICATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="investor_profile",
        db_index=True
    )

    # Public Profile
    display_name = models.CharField(max_length=255, db_index=True)
    one_liner = models.CharField(max_length=280, blank=True)
    investment_thesis = models.TextField(blank=True)

    # Investment Focus (Normalized)
    focus_industries = models.ManyToManyField(
        Industry,
        related_name="investors",
        blank=True
    )
    preferred_stages = models.ManyToManyField(
        StartupStage,
        related_name="investors",
        blank=True
    )

    # Ticket Size
    check_size_min = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Minimum investment amount in USD"
    )
    check_size_max = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Maximum investment amount in USD"
    )

    # Location (MVP: single field – scalable later)
    location = models.CharField(
        max_length=150,
        blank=True,
        help_text="e.g. San Francisco, CA | London | Singapore"
    )

    # External Links
    website_url = models.URLField(blank=True, null=True)
    linkedin_url = models.URLField(blank=True, null=True)
    twitter_url = models.URLField(blank=True, null=True)

    # Investor Type
    investor_type = models.CharField(
        max_length=50,
        choices=INVESTOR_TYPE_CHOICES,
        db_index=True
    )

    # System & Workflow
    verified_by_admin = models.BooleanField(default=False, db_index=True)
    application_status = models.CharField(
        max_length=20,
        choices=APPLICATION_STATUS_CHOICES,
        default="approved",
        db_index=True
    )
    created_by_admin = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="admin_created_investors"
    )
    is_active = models.BooleanField(default=True, db_index=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["investor_type"]),
            models.Index(fields=["verified_by_admin"]),
            models.Index(fields=["application_status"]),
            models.Index(fields=["check_size_min"]),
            models.Index(fields=["check_size_max"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["user"], name="unique_investor_per_user")
        ]
        ordering = ["-created_at"]
        verbose_name = "Investor"
        verbose_name_plural = "Investors"

    def __str__(self):
        return f"{self.display_name} ({self.get_investor_type_display()})"