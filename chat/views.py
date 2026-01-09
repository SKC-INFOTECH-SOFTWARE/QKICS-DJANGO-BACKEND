# chat/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import ChatRoom, Message
from .serializers import ChatRoomSerializer, MessageSerializer


class ChatRoomListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        as_user = ChatRoom.objects.filter(user=request.user)
        as_expert = ChatRoom.objects.filter(expert=request.user)

        rooms = (as_user | as_expert).distinct().order_by("-last_message_at")
        serializer = ChatRoomSerializer(
            rooms, many=True, context={"request": request}
        )
        return Response(serializer.data)


class ChatRoomMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, room_id):
        room = get_object_or_404(
            ChatRoom.objects.filter(
                id=room_id, user=request.user
            ) | ChatRoom.objects.filter(
                id=room_id, expert=request.user
            )
        )

        messages = room.messages.all().order_by("timestamp")
        serializer = MessageSerializer(
            messages, many=True, context={"request": request}
        )
        return Response(serializer.data)
