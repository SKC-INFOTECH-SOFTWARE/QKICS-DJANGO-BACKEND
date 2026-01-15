import os
from decouple import config

# 1️⃣ Set settings module FIRST
env = config("PROJECT_ENV", default="development").lower()

if env == "prod":
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "rplatform.settings.production"
    )
else:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "rplatform.settings.development"
    )

# 2️⃣ Initialize Django apps FIRST
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

# 3️⃣ ONLY NOW import Channels + your code
from channels.routing import ProtocolTypeRouter, URLRouter
from chat.routing import websocket_urlpatterns
from chat.middleware import JWTAuthMiddleware

# 4️⃣ Build ASGI application
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})
