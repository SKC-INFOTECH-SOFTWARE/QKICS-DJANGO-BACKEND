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
    except Exception:
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        print("🧪 JWT MIDDLEWARE HIT")
        print("PATH:", scope.get("path"))
        print("QUERY:", scope.get("query_string"))

        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token")

        if token:
            scope["user"] = await get_user(token[0])
            print("JWT USER:", scope["user"])
        else:
            print("NO TOKEN")
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)