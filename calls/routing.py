from django.urls import re_path
from .consumers import CallChatConsumer

websocket_urlpatterns = [
    re_path(r"^ws/calls/(?P<room_id>[0-9a-f-]+)/$", CallChatConsumer.as_asgi()),
]
