"""
Guest sessions for meeting links.

Someone without a Qkics account joins by typing a display name. They get a
signed, short-lived token that identifies their MeetingGuest row — enough to
open the in-call chat WebSocket, nothing else. It is deliberately NOT a JWT and
grants no access to any other part of the API.
"""
import logging

from django.core import signing

logger = logging.getLogger(__name__)

SALT = "meetings.guest"

# A guest session is only useful for the length of a meeting.
MAX_AGE_SECONDS = 6 * 60 * 60


def issue_guest_token(guest) -> str:
    return signing.dumps(
        {"g": str(guest.id), "m": str(guest.meeting_id)}, salt=SALT
    )


def resolve_guest_token(token: str):
    """Return the MeetingGuest for `token`, or None if invalid/expired."""
    from meetings.models import MeetingGuest

    if not token:
        return None
    try:
        payload = signing.loads(token, salt=SALT, max_age=MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("resolve_guest_token failed: %s", e)
        return None

    return (
        MeetingGuest.objects.select_related("meeting")
        .filter(id=payload.get("g"), meeting_id=payload.get("m"))
        .first()
    )


def clean_display_name(raw: str) -> str:
    """Trim and strip control characters from a guest-supplied name."""
    name = " ".join((raw or "").split())
    name = "".join(ch for ch in name if ch.isprintable())
    return name[:60]
