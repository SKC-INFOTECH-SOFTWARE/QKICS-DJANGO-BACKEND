from chat.models import ChatRoom
from django.db import transaction


@transaction.atomic
def get_or_create_chat_room(*, user, expert):
    """
    Create permanent chat room between user and expert.
    Safe to call multiple times.
    """

    room, created = ChatRoom.objects.get_or_create(
        user=user,
        expert=expert,
    )

    return room
