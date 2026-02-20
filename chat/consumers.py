import json
from channels.generic.websocket import AsyncWebsocketConsumer  # type: ignore
from asgiref.sync import sync_to_async as database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message, ReadReceipt

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        print("🔥 CONSUMER CONNECT HIT")
        print("USER IN SCOPE:", self.scope.get("user"))

        # ❌ Reject unauthenticated users
        if not self.scope["user"].is_authenticated:
            print("❌ UNAUTHENTICATED — CLOSING")
            await self.close(code=4001)
            return

        # ✅ FIX: assign user properly
        self.user = self.scope["user"]

        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        print("✅ WS ACCEPTED")

        # Optional: notify others user is online
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_online",
                "user_id": self.user.id,
            }
        )

    async def disconnect(self, close_code):
        # ✅ Safe disconnect
        if hasattr(self, "room_group_name") and hasattr(self, "user"):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_offline",
                    "user_id": self.user.id,
                }
            )

            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get("type")

        if msg_type == "chat_message":
            message = await self.save_message(
                text=data.get("text"),
                file=data.get("file")
            )

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": message.id,
                        "text": message.text,
                        "file": message.file.url if message.file else None,
                        "sender": message.sender.username,
                        "sender_id": message.sender.id,
                        "timestamp": message.timestamp.isoformat(),
                    },
                }
            )

        elif msg_type == "typing":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_status",
                    "user": self.user.username,
                    "user_id": self.user.id,
                    "is_typing": data.get("is_typing", False),
                }
            )

        elif msg_type == "message_read":
            await self.mark_as_read(data.get("message_id"))

    # ======================
    # Group Event Handlers
    # ======================

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat_message",
            **event["message"]
        }))

    async def typing_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user": event["user"],
            "user_id": event["user_id"],
            "is_typing": event["is_typing"],
        }))

    async def user_online(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_status",
            "user_id": event["user_id"],
            "online": True,
        }))

    async def user_offline(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_status",
            "user_id": event["user_id"],
            "online": False,
        }))

    # ======================
    # Database Helpers
    # ======================

    @database_sync_to_async
    def save_message(self, text, file):
        room = ChatRoom.objects.get(id=self.room_id)

        message = Message.objects.create(
            room=room,
            sender=self.user,
            text=text,
            file=file,
        )

        room.last_message_at = message.timestamp
        room.save(update_fields=["last_message_at"])

        return message

    @database_sync_to_async
    def get_unread_count(self):
        room = ChatRoom.objects.get(id=self.room_id)

        return Message.objects.filter(
            room=room
        ).exclude(
            readreceipt__user=self.user
        ).count()

    @database_sync_to_async
    def mark_as_read(self, message_id):
        if not message_id:
            return
        try:
            message = Message.objects.get(id=message_id)
            ReadReceipt.objects.get_or_create(message=message, user=self.user)
            message.is_read = True
            message.save(update_fields=["is_read"])
        except Message.DoesNotExist:
            return
