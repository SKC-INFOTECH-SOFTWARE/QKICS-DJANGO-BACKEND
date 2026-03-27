import os
from decouple import config

env = config("PROJECT_ENV", default="development").lower()
if env == "prod":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rplatform.settings.production")
else:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rplatform.settings.development")

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from chat.routing import websocket_urlpatterns as chat_ws
from calls.routing import websocket_urlpatterns as calls_ws
from chat.middleware import JWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(chat_ws + calls_ws)
    ),
})
