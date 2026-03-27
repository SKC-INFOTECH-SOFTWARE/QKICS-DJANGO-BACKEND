import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class CallChatConsumer(AsyncWebsocketConsumer):
    """
    In-call chat WebSocket.
    WebRTC signaling → LiveKit handles directly.
    This consumer → text chat, file notifications, typing only.

    URL: ws/calls/<room_id>/
    """

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        self.user       = self.scope["user"]
        self.room_id    = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"callchat_{self.room_id}"

        if not await self._check_access():
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")

        if msg_type == "call_message":
            text = data.get("text", "").strip()
            if not text:
                return
            message = await self._save_message(text)
            await self.channel_layer.group_send(self.group_name, {
                "type":            "broadcast_message",
                "message_id":      message.id,
                "text":            text,
                "sender_id":       self.user.id,
                "sender_username": self.user.username,
                "timestamp":       message.created_at.isoformat(),
            })

        elif msg_type == "file_shared":
            await self.channel_layer.group_send(self.group_name, {
                "type":            "broadcast_file",
                "message_id":      data.get("message_id"),
                "file_name":       data.get("file_name"),
                "file_url":        data.get("file_url"),
                "file_size_bytes": data.get("file_size_bytes"),
                "sender_id":       self.user.id,
                "sender_username": self.user.username,
            })

        elif msg_type == "typing":
            await self.channel_layer.group_send(self.group_name, {
                "type":      "broadcast_typing",
                "user_id":   self.user.id,
                "is_typing": data.get("is_typing", False),
            })

    async def broadcast_message(self, event):
        await self.send(text_data=json.dumps({
            "type":            "call_message",
            "message_id":      event["message_id"],
            "text":            event["text"],
            "sender_id":       event["sender_id"],
            "sender_username": event["sender_username"],
            "timestamp":       event["timestamp"],
        }))

    async def broadcast_file(self, event):
        await self.send(text_data=json.dumps({
            "type":            "file_shared",
            "message_id":      event["message_id"],
            "file_name":       event["file_name"],
            "file_url":        event["file_url"],
            "file_size_bytes": event["file_size_bytes"],
            "sender_id":       event["sender_id"],
            "sender_username": event["sender_username"],
        }))

    async def broadcast_typing(self, event):
        if event["user_id"] != self.user.id:
            await self.send(text_data=json.dumps({
                "type":      "typing",
                "user_id":   event["user_id"],
                "is_typing": event["is_typing"],
            }))

    @sync_to_async
    def _check_access(self):
        from calls.models import CallRoom
        try:
            room = CallRoom.objects.get(id=self.room_id)
            return (
                room.status != CallRoom.STATUS_ENDED
                and (room.user_id == self.user.id or room.advisor_id == self.user.id)
            )
        except CallRoom.DoesNotExist:
            return False

    @sync_to_async
    def _save_message(self, text):
        from calls.models import CallMessage
        return CallMessage.objects.create(
            room_id=self.room_id,
            sender=self.user,
            text=text,
        )
