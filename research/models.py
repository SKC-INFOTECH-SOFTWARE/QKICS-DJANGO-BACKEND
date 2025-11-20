from django.db import models
from users.models import User
from django.utils import timezone


class EntrepreneurProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="entrepreneur_profile"
    )
    company_name = models.CharField(max_length=200)
    tagline = models.CharField(max_length=300, blank=True)
    website = models.URLField(blank=True, null=True)
    pitch_deck = models.FileField(upload_to="pitch_decks/", blank=True, null=True)
    problem_statement = models.TextField()
    solution = models.TextField()
    market_size = models.CharField(max_length=200, blank=True)
    traction = models.TextField(blank=True)
    funding_ask = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.company_name}"


class ExpertProfile(models.Model):
    EXPERTISE_CHOICES = (
        ("technical", "Technical"),
        ("business", "Business"),
        ("funding", "Funding"),
        ("legal", "Legal"),
        ("marketing", "Marketing"),
        ("product", "Product"),
        ("other", "Other"),
    )

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="expert_profile"
    )
    bio = models.TextField()
    expertise = models.CharField(max_length=20, choices=EXPERTISE_CHOICES)
    hourly_rate = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    linkedin = models.URLField(blank=True, null=True)
    resume = models.FileField(upload_to="resumes/", blank=True, null=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Expert: {self.user.get_full_name() or self.user.username}"
