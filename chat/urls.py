from django.urls import path
from .views import ChatRoomListView, ChatRoomMessagesView, MarkRoomAsReadView

urlpatterns = [
    path("rooms/", ChatRoomListView.as_view(), name="chat-room-list"),
    path("rooms/<int:room_id>/messages/", ChatRoomMessagesView.as_view(), name="chat-room-messages"),
    path("rooms/<int:room_id>/read/", MarkRoomAsReadView.as_view(), name="chat-room-read"),
]