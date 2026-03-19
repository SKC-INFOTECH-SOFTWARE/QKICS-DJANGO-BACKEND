import uuid
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Notification(models.Model):

    # ─── Status Choices ───
    STATUS_PENDING = "pending"
    STATUS_SENT = "sent"
    STATUS_FAILED = "failed"
    STATUS_READ = "read"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SENT, "Sent"),
        (STATUS_FAILED, "Failed"),
        (STATUS_READ, "Read"),
    ]

    # ─── Channel Choices ───
    CHANNEL_IN_APP = "IN_APP"
    CHANNEL_PUSH = "PUSH"
    CHANNEL_EMAIL = "EMAIL"
    CHANNEL_SMS = "SMS"

    CHANNEL_CHOICES = [
        (CHANNEL_IN_APP, "In App"),
        (CHANNEL_PUSH, "Push"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS"),
    ]

    # ─── Fields ───
    id = models.BigAutoField(primary_key=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    event = models.CharField(max_length=100, db_index=True)

    title = models.CharField(max_length=255)
    body = models.TextField()

    channels = models.JSONField(default=list)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # store any extra data like bookingId, chatRoomId etc.
    data = models.JSONField(null=True, blank=True)

    # track what the external service responded with
    external_response = models.JSONField(null=True, blank=True)

    # if failed, store why
    failure_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["event"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.event} → {self.user} [{self.status}]"

    def mark_as_read(self):
        from django.utils import timezone

        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.status = self.STATUS_READ
            self.save(update_fields=["is_read", "read_at", "status", "updated_at"])
