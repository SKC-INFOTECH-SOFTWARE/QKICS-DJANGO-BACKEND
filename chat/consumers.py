import json
from channels.generic.websocket import AsyncWebsocketConsumer # type: ignore
from asgiref.sync import sync_to_async as database_sync_to_async
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message, ReadReceipt

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print("🔥 CONSUMER CONNECT HIT")
        print("USER IN SCOPE:", self.scope["user"])

        if not self.scope["user"].is_authenticated:
            print("❌ UNAUTHENTICATED — CLOSING")
            await self.close(code=4001)
            return

        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        print("✅ WS ACCEPTED")

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "user_offline",
                    "user_id": self.user.id,
                }
            )
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get("type")

        if msg_type == "chat_message":
            message = await self.save_message(data["text"], data.get("file"))
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": message.id,
                        "text": message.text,
                        "file": message.file.url if message.file else None,
                        "sender": message.sender.username,
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
                    "is_typing": data["is_typing"]
                }
            )

        elif msg_type == "message_read":
            await self.mark_as_read(data["message_id"])

    # Event handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def typing_status(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user": event["user"],
            "is_typing": event["is_typing"]
        }))

    async def user_online(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_status",
            "user_id": event["user_id"],
            "online": True
        }))

    async def user_offline(self, event):
        await self.send(text_data=json.dumps({
            "type": "user_status",
            "user_id": event["user_id"],
            "online": False
        }))

    # Database helpers
    @database_sync_to_async
    def save_message(self, text, file):
        room = ChatRoom.objects.get(id=self.room_id)
        message = Message.objects.create(
            room=room,
            sender=self.user,
            text=text,
            file=file
        )
        room.last_message_at = message.timestamp
        room.save()
        return message

    @database_sync_to_async
    def get_unread_count(self):
        room = ChatRoom.objects.get(id=self.room_id)
        return Message.objects.filter(room=room, read_by__user=self.user).count() == 0

    @database_sync_to_async
    def mark_as_read(self, message_id):
        message = Message.objects.get(id=message_id)
        ReadReceipt.objects.get_or_create(message=message, user=self.user)
        message.is_read = True
        message.save()