from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatRoom(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_rooms_as_user",
        limit_choices_to={"user_type": "normal"},
    )

    advisor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_rooms_as_advisor",
        limit_choices_to={"user_type__in": ["expert", "investor"]},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "advisor")
        ordering = ["-last_message_at"]
        indexes = [
            models.Index(fields=["user", "advisor"]),
            models.Index(fields=["last_message_at"]),
        ]


class Message(models.Model):
    """
    Every message sent in a chat room.
    """

    room = models.ForeignKey(
        ChatRoom, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    text = models.TextField(blank=True)
    file = models.FileField(upload_to="chat/files/", blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["room", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.sender.username}: {self.text[:30] or 'File'}"


class ReadReceipt(models.Model):
    """
    Tracks who has read which message (for "seen" feature)
    """

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="read_by"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("message", "user")
        indexes = [
            models.Index(fields=["message", "user"]),
        ]

    def __str__(self):
        return f"{self.user.username} read message {self.message.id}"
