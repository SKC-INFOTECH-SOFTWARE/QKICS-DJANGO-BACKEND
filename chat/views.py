# chat/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework import status
from .models import ChatRoom, Message, ReadReceipt
from .serializers import ChatRoomSerializer, MessageSerializer
from django.db.models import Q


class ChatRoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rooms = (
            ChatRoom.objects.filter(Q(user=request.user) | Q(advisor=request.user))
            .distinct()
            .order_by("-last_message_at")
        )

        serializer = ChatRoomSerializer(rooms, many=True, context={"request": request})
        return Response(serializer.data)


class ChatRoomMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):

        room = get_object_or_404(
            ChatRoom.objects.filter(
                Q(id=room_id, user=request.user) | Q(id=room_id, advisor=request.user)
            )
        )

        messages = room.messages.all().order_by("timestamp")

        serializer = MessageSerializer(
            messages,
            many=True,
            context={"request": request},
        )

        return Response(serializer.data)


class MarkRoomAsReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        user = request.user
        room = get_object_or_404(ChatRoom, id=room_id)

        if user not in [room.user, room.advisor]:
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
