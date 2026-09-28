"""
Admin-created meeting links.

A Meeting is an "entry door" to a regular `calls.CallRoom`: instead of reaching
the room through a booking or an expert slot, participants reach it with a
shareable link built from `invite_token`. Everything downstream — LiveKit,
recording, in-call chat, host mute/remove, auto-cut — is the existing CallRoom
machinery, unchanged.
"""
import secrets
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# Deliberately excludes look-alike characters (0/O, 1/l/I) so a code stays
# readable when someone reads it out or retypes it from a screenshot.
TOKEN_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"
TOKEN_LENGTH = 12


def generate_invite_token() -> str:
    """Short, URL-safe, guess-proof code used in the public meeting link.

    12 chars over a 32-symbol alphabet is ~60 bits — short enough to share in a
    chat message, far too large to enumerate. Links also expire
    (`LINK_GRACE_HOURS`) and can be revoked with `rotate_invite_token()`.
    """
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


class Meeting(models.Model):
    # Access
    INVITED_ONLY = "INVITED_ONLY"
    ANYONE_WITH_LINK = "ANYONE_WITH_LINK"
    ACCESS_CHOICES = (
        (INVITED_ONLY, "Only invited users"),
        (ANYONE_WITH_LINK, "Anyone with the link"),
    )

    # Lifecycle
    STATUS_SCHEDULED = "SCHEDULED"
    STATUS_LIVE = "LIVE"
    STATUS_ENDED = "ENDED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_CHOICES = (
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_LIVE, "Live"),
        (STATUS_ENDED, "Ended"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    # Recordings of admin meetings are kept for a shorter window than normal
    # consultation calls (calls.CallRecording.RETENTION_DAYS) and are then
    # deleted from the server by the `cleanup_recordings` cron.
    RECORDING_RETENTION_DAYS = 3

    # Participants may enter this long before the scheduled start.
    JOIN_WINDOW_MINUTES = 10

    # A link stays usable this long after the scheduled end (or after creation
    # for an instant meeting) before it is considered expired.
    LINK_GRACE_HOURS = 12

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meetings_hosted",
    )

    invite_token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        default=generate_invite_token,
    )

    access_mode = models.CharField(
        max_length=20,
        choices=ACCESS_CHOICES,
        default=ANYONE_WITH_LINK,
    )

    # Null start = instant meeting ("start now"), joinable immediately.
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)

    max_participants = models.PositiveIntegerField(default=20)

    # Nobody but the host can enter until the host has joined once.
    require_host = models.BooleanField(default=False)

    # Let people without a Qkics account join by typing a display name.
    # Only meaningful for ANYONE_WITH_LINK — an invite list needs accounts.
    allow_guests = models.BooleanField(default=True)

    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        db_index=True,
    )

    call_room = models.OneToOneField(
        "calls.CallRoom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="meeting",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_start"]),
            models.Index(fields=["host", "status"]),
        ]

    def __str__(self):
        return f"{self.title} [{self.status}]"

    # ── link / timing helpers ─────────────────────────────────────────

    @property
    def is_open(self):
        """Neither ended nor cancelled."""
        return self.status in (self.STATUS_SCHEDULED, self.STATUS_LIVE)

    @property
    def link_expires_at(self):
        base = self.scheduled_end or self.scheduled_start or self.created_at
        return base + timezone.timedelta(hours=self.LINK_GRACE_HOURS)

    @property
    def is_expired(self):
        return timezone.now() > self.link_expires_at

    def can_join_now(self):
        """Whether the join window is open right now (ignores per-user access)."""
        if not self.is_open or self.is_expired:
            return False
        if not self.scheduled_start:
            return True  # instant meeting
        opens_at = self.scheduled_start - timezone.timedelta(
            minutes=self.JOIN_WINDOW_MINUTES
        )
        return timezone.now() >= opens_at

    def join_opens_at(self):
        if not self.scheduled_start:
            return None
        return self.scheduled_start - timezone.timedelta(
            minutes=self.JOIN_WINDOW_MINUTES
        )

    def rotate_invite_token(self):
        """Kill the old link immediately and return the new token."""
        self.invite_token = generate_invite_token()
        self.save(update_fields=["invite_token", "updated_at"])
        return self.invite_token


class MeetingInvite(models.Model):
    """Who the link was sent to. Also the allow-list for INVITED_ONLY meetings."""

    id = models.BigAutoField(primary_key=True)

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="invites"
    )

    # A registered user, or just an email address for someone off-platform.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="meeting_invites",
    )
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=150, blank=True)

    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["invited_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_meeting_invite_per_user",
            ),
        ]
        indexes = [models.Index(fields=["meeting", "user"])]

    def __str__(self):
        who = self.user.username if self.user_id else (self.email or "unknown")
        return f"{who} → {self.meeting_id}"

    @property
    def display_name(self):
        if self.user_id:
            return self.user.get_full_name() or self.user.username
        return self.name or self.email


class MeetingGuest(models.Model):
    """Someone who joined by link without a Qkics account.

    Identified only by the name they typed plus an opaque id. The id becomes
    their LiveKit identity (``guest_<uuid>``) so host mute/remove works on them
    exactly as on a signed-in participant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="guests"
    )
    display_name = models.CharField(max_length=60)

    joined_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["joined_at"]
        indexes = [models.Index(fields=["meeting", "joined_at"])]

    def __str__(self):
        return f"{self.display_name} (guest)"

    @property
    def livekit_identity(self):
        return f"guest_{self.id}"
