import logging
import requests

from rplatform.settings.base import NOTIFICATION_API_KEY, NOTIFICATION_SERVICE_URL, DEFAULT_CHANNELS

logger = logging.getLogger(__name__)




def _headers():
    return {
        "x-api-key": NOTIFICATION_API_KEY,
        "Content-Type": "application/json",
    }


def send_notification(
    *,
    event: str,
    user_id: str,
    title: str,
    body: str,
    channels: list = None,
    user_email: str = None,
    user_mobile: str = None,
    data: dict = None,
):
    """
    Core function. Sends a notification via the external notification service.

    Args:
        event:        Event name string (e.g. "BOOKING_CONFIRMED")
        user_id:      The user's ID (string) — required for IN_APP and PUSH
        title:        Notification title / subject
        body:         Notification body text
        channels:     List of channels e.g. ["IN_APP", "PUSH", "EMAIL"]
        user_email:   Required if EMAIL is in channels
        user_mobile:  Required if SMS is in channels
        data:         Optional dict passed as payload metadata

    Returns:
        dict | None: The parsed JSON response, or None on failure.
    """
    if not NOTIFICATION_API_KEY:
        logger.warning("NOTIFICATION_API_KEY is not set. Skipping notification.")
        return None

    if channels is None:
        channels = DEFAULT_CHANNELS

    user_payload = {"id": str(user_id)}
    if user_email:
        user_payload["email"] = user_email
    if user_mobile:
        user_payload["mobile"] = user_mobile

    payload = {
        "event": event,
        "user": user_payload,
        "channels": channels,
        "title": title,
        "body": body,
    }

    if data:
        payload["data"] = data

    try:
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/api/notifications/send",
            json=payload,
            headers=_headers(),
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        logger.error("Notification service timed out for event: %s", event)
    except requests.exceptions.RequestException as e:
        logger.error("Notification service error for event %s: %s", event, str(e))

    return None


def get_notifications(*, user_id: str, channel: str = "IN_APP", limit: int = 20):
    """
    Fetch stored notifications for a user.
    Used to power the frontend notification bell.
    """
    if not NOTIFICATION_API_KEY:
        return None

    try:
        response = requests.get(
            f"{NOTIFICATION_SERVICE_URL}/api/notifications",
            headers=_headers(),
            params={"userId": str(user_id), "channel": channel, "limit": limit},
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch notifications for user %s: %s", user_id, str(e))
    return None


def mark_notification_read(*, notification_id: str):
    """
    Mark a single in-app notification as read.
    """
    if not NOTIFICATION_API_KEY:
        return None

    try:
        response = requests.patch(
            f"{NOTIFICATION_SERVICE_URL}/api/notifications/{notification_id}/read",
            headers=_headers(),
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(
            "Failed to mark notification %s as read: %s", notification_id, str(e)
        )
    return None


def register_push_token(
    *, user_id: str, token: str, platform: str, device_id: str = None
):
    """
    Register an FCM push token for a device.
    Call this after login from the mobile/web client.

    platform: "android" | "ios" | "web"
    """
    if not NOTIFICATION_API_KEY:
        return None

    payload = {
        "userId": str(user_id),
        "token": token,
        "platform": platform,
    }
    if device_id:
        payload["deviceId"] = device_id

    try:
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/api/push-tokens/register",
            json=payload,
            headers=_headers(),
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to register push token for user %s: %s", user_id, str(e))
    return None


def unregister_push_token(*, token: str):
    """
    Remove a push token. Call this on logout.
    """
    if not NOTIFICATION_API_KEY:
        return None

    try:
        response = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/api/push-tokens/unregister",
            json={"token": token},
            headers=_headers(),
            timeout=5,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to unregister push token: %s", str(e))
    return None
