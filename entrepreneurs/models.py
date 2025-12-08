from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class EntrepreneurProfile(models.Model):
    APPLICATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    FUNDING_STAGE_CHOICES = [
        ("pre_seed", "Pre-Seed"),
        ("seed", "Seed"),
        ("series_a", "Series A"),
        ("series_b", "Series B+"),
        ("bootstrapped", "Bootstrapped"),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="entrepreneur_profile"
    )

    # Basic Startup Information
    startup_name = models.CharField(max_length=255)
    one_liner = models.CharField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True, null=True)
    logo = models.ImageField(upload_to="entrepreneurs/logos/", blank=True, null=True)

    # Essential Filters
    industry = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)

    # Funding Stage
    funding_stage = models.CharField(
        max_length=30, choices=FUNDING_STAGE_CHOICES, blank=True
    )

    # Verification
    verified_by_admin = models.BooleanField(default=False)
    application_status = models.CharField(
        max_length=20, choices=APPLICATION_STATUS_CHOICES, default="draft"
    )
    
    application_note = models.TextField(blank=True, null=True)
    admin_review_note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.startup_name} – {self.user.username}"