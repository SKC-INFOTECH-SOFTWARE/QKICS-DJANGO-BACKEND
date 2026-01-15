# chat/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework import status
from .models import ChatRoom, Message, ReadReceipt
from .serializers import ChatRoomSerializer, MessageSerializer


class ChatRoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_user = ChatRoom.objects.filter(user=request.user)
        as_expert = ChatRoom.objects.filter(expert=request.user)

        rooms = (as_user | as_expert).distinct().order_by("-last_message_at")
        serializer = ChatRoomSerializer(rooms, many=True, context={"request": request})
        return Response(serializer.data)


class ChatRoomMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(
            ChatRoom.objects.filter(id=room_id, user=request.user)
            | ChatRoom.objects.filter(id=room_id, expert=request.user)
        )

        messages = room.messages.all().order_by("timestamp")
        serializer = MessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)


class MarkRoomAsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        user = request.user
        room = get_object_or_404(ChatRoom, id=room_id)

        booking = room.booking

        if user not in [booking.user, booking.expert]:
            return Response(
                {"status": "error", "message": "Not allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )

        unread_messages = Message.objects.filter(room=room).exclude(sender=user)

        receipts = [
            ReadReceipt(user=user, message=msg)
            for msg in unread_messages
            if not ReadReceipt.objects.filter(user=user, message=msg).exists()
        ]

        ReadReceipt.objects.bulk_create(receipts)

        return Response(
            {
                "status": "success",
                "room_id": room_id,
                "read_count": len(receipts),
            }
        )
