import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class CallChatConsumer(AsyncWebsocketConsumer):
    """
    In-call chat WebSocket.
    WebRTC signaling → LiveKit handles directly.
    This consumer → text chat, file notifications, typing, host chat-blocks.

    URL: ws/calls/<room_id>/
    """

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close(code=4001)
            return

        self.user       = self.scope["user"]
        self.room_id    = self.scope["url_route"]["kwargs"]["room_id"]
        self.group_name = f"callchat_{self.room_id}"
        self.is_host    = False
        self.is_blocked = False
        self.blocked_ids = set()

        access = await self._load_access()
        if not access:
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Tell the client the current block state (host UI + blocked user).
        await self.send(text_data=json.dumps({
            "type": "chat_block_state",
            "blocked_user_ids": [str(i) for i in self.blocked_ids],
        }))

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
            if self.is_blocked:
                await self.send(text_data=json.dumps({"type": "chat_blocked_notice"}))
                return
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
            if self.is_blocked:
                await self.send(text_data=json.dumps({"type": "chat_blocked_notice"}))
                return
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
            if self.is_blocked:
                return
            await self.channel_layer.group_send(self.group_name, {
                "type":      "broadcast_typing",
                "user_id":   self.user.id,
                "is_typing": data.get("is_typing", False),
            })

        elif msg_type == "block_user":
            # Only the host may block/unblock a participant from chatting.
            if not self.is_host:
                return
            target = data.get("user_id")
            blocked = bool(data.get("blocked", True))
            if target is None or str(target) == str(self.user.id):
                return
            try:
                ids = await self._set_block(int(target), blocked)
            except (TypeError, ValueError):
                return
            await self.channel_layer.group_send(self.group_name, {
                "type":             "chat_block_changed",
                "user_id":          str(target),
                "blocked":          blocked,
                "blocked_user_ids": [str(i) for i in ids],
            })

    # ───────── group event handlers ─────────

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

    async def chat_block_changed(self, event):
        # Keep this connection's own block flag authoritative.
        if event["user_id"] == str(self.user.id):
            self.is_blocked = event["blocked"]
        await self.send(text_data=json.dumps({
            "type":             "chat_block_changed",
            "user_id":          event["user_id"],
            "blocked":          event["blocked"],
            "blocked_user_ids": event["blocked_user_ids"],
        }))

    # ───────── DB helpers ─────────

    @sync_to_async
    def _load_access(self):
        """Load room, resolve host/blocked state, and check membership.

        Returns True if this user may join the chat, else False.
        """
        from calls.models import CallRoom
        from bookings.models import Booking

        try:
            room = CallRoom.objects.get(id=self.room_id)
        except CallRoom.DoesNotExist:
            return False

        if room.status == CallRoom.STATUS_ENDED:
            return False

        uid = self.user.id

        if room.slot_id is not None:  # batch (group) room
            if room.advisor_id == uid:
                ok = True
            else:
                ok = Booking.objects.filter(
                    slot_id=room.slot_id,
                    user_id=uid,
                    status=Booking.STATUS_CONFIRMED,
                ).exists()
        else:  # one-to-one room
            ok = room.user_id == uid or room.advisor_id == uid

        if not ok:
            return False

        self.is_host = room.advisor_id == uid
        self.blocked_ids = set(room.chat_blocked_user_ids or [])
        self.is_blocked = uid in self.blocked_ids
        return True

    @sync_to_async
    def _set_block(self, target_id, blocked):
        from calls.models import CallRoom
        room = CallRoom.objects.get(id=self.room_id)
        ids = set(room.chat_blocked_user_ids or [])
        if blocked:
            ids.add(target_id)
        else:
            ids.discard(target_id)
        room.chat_blocked_user_ids = list(ids)
        room.save(update_fields=["chat_blocked_user_ids", "updated_at"])
        return list(ids)

    @sync_to_async
    def _save_message(self, text):
        from calls.models import CallMessage
        return CallMessage.objects.create(
            room_id=self.room_id,
            sender=self.user,
            text=text,
        )
