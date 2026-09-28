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


@sync_to_async
def get_meeting_guest(token):
    """Resolve a meeting guest session token (see meetings.services.guest_auth).

    Guests have no Django user; the consumer reads `scope["meeting_guest"]`.
    """
    from meetings.services.guest_auth import resolve_guest_token

    try:
        return resolve_guest_token(token)
    except Exception as e:
        print("GUEST TOKEN ERROR:", e)
        return None


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope["query_string"].decode())
        token = query_string.get("token")
        guest_token = query_string.get("guest")

        scope["meeting_guest"] = None

        if token:
            scope["user"] = await get_user(token[0])
        else:
            scope["user"] = AnonymousUser()

        # Only fall back to a guest session when there is no signed-in user.
        if not scope["user"].is_authenticated and guest_token:
            scope["meeting_guest"] = await get_meeting_guest(guest_token[0])

        return await super().__call__(scope, receive, send)
