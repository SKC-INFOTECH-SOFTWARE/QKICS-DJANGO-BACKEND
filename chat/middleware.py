from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from asgiref.sync import sync_to_async


@sync_to_async
def get_user(token):
    jwt_auth = JWTAuthentication()
    try:
        validated_token = jwt_auth.get_validated_token(token)
        return jwt_auth.get_user(validated_token)
    except Exception as e:
        print("JWT ERROR:", e)
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):

        # ✅ DEV MODE BYPASS
        if scope["server"][0] in ("127.0.0.1", "localhost"):
            from django.contrib.auth import get_user_model

            User = get_user_model()
            scope["user"] = await sync_to_async(User.objects.first)()
            return await super().__call__(scope, receive, send)

        # 🔐 PROD MODE (unchanged)
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token")

        if token:
            scope["user"] = await get_user(token[0])
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)
