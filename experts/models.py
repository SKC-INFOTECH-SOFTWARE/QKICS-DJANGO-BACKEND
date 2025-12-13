from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class ExpertProfile(models.Model):
    APPLICATION_STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    uuid = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True
    )

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="expert_profile"
    )

    # ---- Basic Identity ----
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    headline = models.CharField(max_length=255, blank=True)
    profile_picture = models.ImageField(
        upload_to="experts/profile_pictures/", null=True, blank=True
    )

    # ---- Expertise ----
    primary_expertise = models.CharField(max_length=255, blank=True)
    other_expertise = models.TextField(blank=True)

    # ---- Consultation Info ----
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_available = models.BooleanField(default=True)

    # ---- Application / Verification ----
    verified_by_admin = models.BooleanField(default=False)
    application_status = models.CharField(
        max_length=20, choices=APPLICATION_STATUS_CHOICES, default="draft"
    )
    application_submitted_at = models.DateTimeField(null=True, blank=True)
    admin_review_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"ExpertProfile of {self.user.username}"


# ===============================
# Experience (LinkedIn style)
# ===============================
class ExpertExperience(models.Model):
    EMPLOYMENT_TYPES = [
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("internship", "Internship"),
        ("contract", "Contract"),
        ("freelance", "Freelance"),
        ("research", "Research"),
        ("other", "Other"),
    ]

    expert = models.ForeignKey(
        ExpertProfile, on_delete=models.CASCADE, related_name="experiences"
    )
    job_title = models.CharField(max_length=255)
    company = models.CharField(max_length=255, blank=True)
    employment_type = models.CharField(
        max_length=30, choices=EMPLOYMENT_TYPES, default="full_time"
    )
    location = models.CharField(max_length=255, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.job_title} - {self.expert.user.username}"


# ===============================
# Education (LinkedIn style)
# ===============================
class ExpertEducation(models.Model):
    expert = models.ForeignKey(
        ExpertProfile, on_delete=models.CASCADE, related_name="educations"
    )
    school = models.CharField(max_length=255)
    degree = models.CharField(max_length=255, blank=True)
    field_of_study = models.CharField(max_length=255, blank=True)
    start_year = models.PositiveIntegerField(null=True, blank=True)
    end_year = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-end_year", "-start_year"]

    def __str__(self):
        return f"{self.degree} at {self.school} - {self.expert.user.username}"


# ===============================
# Certifications (LinkedIn style)
# ===============================
class ExpertCertification(models.Model):
    expert = models.ForeignKey(
        ExpertProfile, on_delete=models.CASCADE, related_name="certifications"
    )
    name = models.CharField(max_length=255)
    issuing_organization = models.CharField(max_length=255, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    credential_id = models.CharField(max_length=255, blank=True)
    credential_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date"]

    def __str__(self):
        return f"{self.name} - {self.expert.user.username}"


# ===============================
# Honors / Awards (LinkedIn style)
# ===============================
class ExpertHonorAward(models.Model):
    expert = models.ForeignKey(
        ExpertProfile, on_delete=models.CASCADE, related_name="honors_awards"
    )
    title = models.CharField(max_length=255)
    issuer = models.CharField(max_length=255, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-issue_date"]

    def __str__(self):
        return f"{self.title} - {self.expert.user.username}"
