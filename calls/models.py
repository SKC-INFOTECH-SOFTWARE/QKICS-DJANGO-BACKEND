import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class CallRoom(models.Model):
    STATUS_WAITING = "WAITING"
    STATUS_ACTIVE  = "ACTIVE"
    STATUS_ENDED   = "ENDED"

    STATUS_CHOICES = (
        (STATUS_WAITING, "Waiting"),
        (STATUS_ACTIVE,  "Active"),
        (STATUS_ENDED,   "Ended"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    booking = models.OneToOneField(
        "bookings.Booking", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="call_room",
    )
    investor_booking = models.OneToOneField(
        "bookings.InvestorBooking", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="call_room",
    )

    user    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="call_rooms_as_user")
    advisor = models.ForeignKey(User, on_delete=models.CASCADE, related_name="call_rooms_as_advisor")

    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_WAITING, db_index=True)
    sfu_room_name = models.CharField(max_length=255, blank=True)

    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end   = models.DateTimeField(null=True, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at   = models.DateTimeField(null=True, blank=True)

    auto_cut_scheduled = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["advisor", "status"]),
            models.Index(fields=["scheduled_end"]),
        ]

    def __str__(self):
        return f"CallRoom {self.id} | {self.user} ↔ {self.advisor} [{self.status}]"

    @property
    def duration_seconds(self):
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds())
        return None

    def can_join(self):
        if self.status == self.STATUS_ENDED:
            return False
        if not self.scheduled_start:
            return True
        return timezone.now() >= (self.scheduled_start - timezone.timedelta(minutes=5))


class CallParticipant(models.Model):
    id   = models.BigAutoField(primary_key=True)
    room = models.ForeignKey(CallRoom, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="call_participations")

    joined_at     = models.DateTimeField(auto_now_add=True)
    left_at       = models.DateTimeField(null=True, blank=True)
    connection_id = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["-joined_at"]
        indexes  = [models.Index(fields=["room", "user"])]

    @property
    def duration_seconds(self):
        if self.left_at:
            return int((self.left_at - self.joined_at).total_seconds())
        return None


class CallRecording(models.Model):
    STATUS_RECORDING  = "RECORDING"   # egress chal raha hai, local file ban rahi hai
    STATUS_UPLOADING  = "UPLOADING"   # Cloudinary par upload ho raha hai
    STATUS_READY      = "READY"       # Cloudinary par available hai
    STATUS_DELETED    = "DELETED"     # 7 din baad delete ho gaya
    STATUS_FAILED     = "FAILED"      # kuch error aaya

    STATUS_CHOICES = (
        (STATUS_RECORDING,  "Recording"),
        (STATUS_UPLOADING,  "Uploading"),
        (STATUS_READY,      "Ready"),
        (STATUS_DELETED,    "Deleted"),
        (STATUS_FAILED,     "Failed"),
    )

    RETENTION_DAYS = 7

    id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(CallRoom, on_delete=models.CASCADE, related_name="recordings")

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES,
        default=STATUS_RECORDING, db_index=True,
    )

    # Cloudinary fields
    # public_id  = Cloudinary mein file ka unique ID (delete/download ke liye)
    # secure_url = HTTPS URL (admin direct access ke liye, signed)
    cloudinary_public_id = models.CharField(max_length=500, blank=True)
    cloudinary_secure_url = models.CharField(max_length=1000, blank=True)

    # LiveKit egress tracking
    egress_id = models.CharField(max_length=255, blank=True)

    # Local file path (temporary — deleted after Cloudinary upload)
    local_file_path = models.CharField(max_length=500, blank=True)

    file_size_bytes  = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    started_at   = models.DateTimeField(auto_now_add=True)
    ended_at     = models.DateTimeField(null=True, blank=True)
    delete_after = models.DateTimeField(db_index=True)
    deleted_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes  = [models.Index(fields=["status", "delete_after"])]

    def save(self, *args, **kwargs):
        if not self.delete_after:
            self.delete_after = timezone.now() + timezone.timedelta(days=self.RETENTION_DAYS)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Recording {self.id} [{self.status}]"


class CallMessage(models.Model):
    id     = models.BigAutoField(primary_key=True)
    room   = models.ForeignKey(CallRoom, on_delete=models.CASCADE, related_name="call_messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_call_messages")

    text            = models.TextField(blank=True)
    file            = models.FileField(upload_to="call_files/", blank=True, null=True)
    file_name       = models.CharField(max_length=255, blank=True)
    file_size_bytes = models.IntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes  = [models.Index(fields=["room", "created_at"])]

    def __str__(self):
        return f"{self.sender.username}: {self.text[:40] or 'File'}"


class CallNote(models.Model):
    """
    Private notes — only the owner can read/edit.
    Never exposed to the other participant.
    Persists after call ends indefinitely.
    """
    id   = models.BigAutoField(primary_key=True)
    room = models.ForeignKey(CallRoom, on_delete=models.CASCADE, related_name="notes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="call_notes")

    content = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("room", "user")
        ordering        = ["-updated_at"]
        indexes         = [models.Index(fields=["room", "user"])]

    def __str__(self):
        return f"Note by {self.user.username} in {self.room_id}"
