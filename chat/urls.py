from django.urls import path
from .views import ChatRoomListView, ChatRoomMessagesView

urlpatterns = [
    path("rooms/", ChatRoomListView.as_view(), name="chat-room-list"),
    path("rooms/<int:room_id>/messages/", ChatRoomMessagesView.as_view(), name="chat-room-messages"),
]