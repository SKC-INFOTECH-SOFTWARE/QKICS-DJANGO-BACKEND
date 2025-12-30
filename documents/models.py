import uuid
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


# =====================================================
# DOCUMENT MODEL
# =====================================================
class Document(models.Model):
    """
    Represents a document uploaded by admin.
    Access is controlled via subscription or payment.
    """

    class AccessType(models.TextChoices):
        FREE = "FREE", "Free"
        PREMIUM = "PREMIUM", "Premium"
        PAID = "PAID", "Paid"

    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    file = models.FileField(upload_to="documents/")

    access_type = models.CharField(
        max_length=10,
        choices=AccessType.choices,
        default=AccessType.FREE,
        help_text="Controls who can access this document",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Disable document without deleting it",
    )

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_documents",
        help_text="Admin who uploaded this document",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


# =====================================================
# DOCUMENT DOWNLOAD (HISTORY) MODEL
# =====================================================
class DocumentDownload(models.Model):
    """
    Tracks each successful document download.
    One row = one download.
    Used for enforcing monthly limits and audit.
    """

    class AccessTypeSnapshot(models.TextChoices):
        FREE = "FREE", "Free"
        PREMIUM = "PREMIUM", "Premium"
        PAID = "PAID", "Paid"

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="document_downloads",
    )

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="downloads",
    )

    access_type_snapshot = models.CharField(
        max_length=10,
        choices=AccessTypeSnapshot.choices,
        help_text="Access type at the time of download",
    )

    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-downloaded_at"]
        indexes = [
            models.Index(fields=["user", "downloaded_at"]),
            models.Index(fields=["document"]),
        ]

    def __str__(self):
        return f"{self.user} downloaded {self.document}"
