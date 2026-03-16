import uuid
import mimetypes
from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.db.models import Q

User = settings.AUTH_USER_MODEL


# =====================================================
# COMPANY MODEL
# =====================================================


class Company(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("suspended", "Suspended"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)

    logo = models.ImageField(upload_to="companies/logos/", null=True, blank=True)
    cover_image = models.ImageField(
        upload_to="companies/covers/", null=True, blank=True
    )

    description = models.TextField(blank=True)

    industry = models.CharField(max_length=255, blank=True)

    website = models.URLField(blank=True)
    location = models.CharField(max_length=255, blank=True)

    owner = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_companies",
    )

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def save(self, *args, **kwargs):

        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1

            while Company.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =====================================================
# COMPANY MEMBER MODEL
# =====================================================


class CompanyMember(models.Model):

    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("editor", "Editor"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="members", db_index=True
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="company_memberships",
        db_index=True,
    )

    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("company", "user")
        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["user"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["company"],
                condition=Q(role="owner"),
                name="unique_company_owner",
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.role} ({self.company})"


# =====================================================
# COMPANY POST MODEL
# =====================================================


class CompanyPost(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="posts", db_index=True
    )

    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="company_posts", db_index=True
    )

    title = models.CharField(max_length=255)

    content = models.TextField()

    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=False)

    payment = models.ForeignKey(
        "payments.Payment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="company_posts",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self):

        if self.company.status != "approved":
            raise ValidationError("Company is not approved to create posts.")

    def __str__(self):
        return self.title


# =====================================================
# COMPANY POST MEDIA MODEL
# =====================================================


class CompanyPostMedia(models.Model):

    MEDIA_TYPE = (
        ("image", "Image"),
        ("video", "Video"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    post = models.ForeignKey(
        CompanyPost, on_delete=models.CASCADE, related_name="media", db_index=True
    )

    file = models.FileField(upload_to="company_posts/")

    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["post"]),
        ]

    def save(self, *args, **kwargs):

        mime_type, _ = mimetypes.guess_type(self.file.name)

        if mime_type:
            if mime_type.startswith("image"):
                self.media_type = "image"
            elif mime_type.startswith("video"):
                self.media_type = "video"
            else:
                raise ValidationError("Unsupported file type")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.media_type} - {self.post.title}"


# ===========================================================
# COMPANY POST SETTINGS MODEL
# ===========================================================
class CompanyPostSettings(models.Model):

    free_posts_per_company = models.PositiveIntegerField(default=5)

    paid_post_price = models.DecimalField(max_digits=10, decimal_places=2, default=100)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Company Post Settings"

    def save(self, *args, **kwargs):
        if not self.pk and CompanyPostSettings.objects.exists():
            raise ValidationError("Only one settings instance allowed")
        super().save(*args, **kwargs)
