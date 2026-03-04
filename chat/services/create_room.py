from chat.models import ChatRoom
from django.db import transaction


@transaction.atomic
def get_or_create_chat_room(*, user, advisor):

    room, created = ChatRoom.objects.get_or_create(
        user=user,
        advisor=advisor,
    )

    return room
