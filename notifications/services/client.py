import logging
import requests

from django.conf import settings

logger = logging.getLogger(__name__)


def _headers():
    return {
        "x-api-key": settings.NOTIFICATION_API_KEY,
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
    Core notification function.

    Flow:
        1. Save notification to local DB (always, regardless of external service)
        2. Send to external notification service
        3. Update local DB record with result (sent / failed)

    Args:
        event:        Event name string (e.g. "BOOKING_CONFIRMED")
        user_id:      The user's ID — required for IN_APP and PUSH
        title:        Notification title / subject
        body:         Notification body text
        channels:     List of channels e.g. ["IN_APP", "PUSH", "EMAIL"]
                      Defaults to settings.DEFAULT_CHANNELS
        user_email:   Required if EMAIL is in channels
        user_mobile:  Required if SMS is in channels
        data:         Optional dict for extra metadata (bookingId, chatRoomId etc.)

    Returns:
        dict | None: The parsed JSON response from external service, or None on failure.
    """
    from notifications.models import Notification
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if channels is None:
        channels = settings.DEFAULT_CHANNELS

    # ─────────────────────────────────────────────
    # STEP 1: Save to local DB first (always)
    # Even if external service is down, we keep a record
    # ─────────────────────────────────────────────
    notification = None
    try:
        user = User.objects.get(id=user_id)
        notification = Notification.objects.create(
            user=user,
            event=event,
            title=title,
            body=body,
            channels=channels,
            data=data or {},
            status=Notification.STATUS_PENDING,
        )
    except User.DoesNotExist:
        logger.error(
            "Cannot save notification — user with id %s does not exist.", user_id
        )
        return None
    except Exception as e:
        logger.error("Failed to save notification to local DB: %s", str(e))
        # Do not stop here — still try to send externally
        # but we won't be able to update status

    # ─────────────────────────────────────────────
    # STEP 2: Check if external service is configured
    # ─────────────────────────────────────────────
    if not settings.NOTIFICATION_API_KEY:
        logger.warning(
            "NOTIFICATION_API_KEY is not set. Notification saved to DB but not sent externally."
        )
        if notification:
            notification.status = Notification.STATUS_FAILED
            notification.failure_reason = "NOTIFICATION_API_KEY not configured"
            notification.save(update_fields=["status", "failure_reason", "updated_at"])
        return None

    # ─────────────────────────────────────────────
    # STEP 3: Build and send payload to external service
    # ─────────────────────────────────────────────
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
            f"{settings.NOTIFICATION_SERVICE_URL}/api/notifications/send",
            json=payload,
            headers=_headers(),
            timeout=10,
        )

        if not response.ok:
            logger.error(
                "Notification service returned %s: %s",
                response.status_code,
                response.text,
            )
            # ── Mark as failed in local DB ──
            if notification:
                notification.status = Notification.STATUS_FAILED
                notification.failure_reason = (
                    f"HTTP {response.status_code}: {response.text[:500]}"
                )
                notification.external_response = {
                    "status_code": response.status_code,
                    "body": response.text[:500],
                }
                notification.save(
                    update_fields=[
                        "status",
                        "failure_reason",
                        "external_response",
                        "updated_at",
                    ]
                )
            return None

        result = response.json()

        # ── Mark as sent in local DB ──
        if notification:
            notification.status = Notification.STATUS_SENT
            notification.external_response = result
            notification.save(
                update_fields=["status", "external_response", "updated_at"]
            )

        return result

    except requests.exceptions.Timeout:
        logger.error("Notification service timed out for event: %s", event)
        if notification:
            notification.status = Notification.STATUS_FAILED
            notification.failure_reason = "Request timed out after 10 seconds"
            notification.save(update_fields=["status", "failure_reason", "updated_at"])

    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to notification service for event: %s", event)
        if notification:
            notification.status = Notification.STATUS_FAILED
            notification.failure_reason = (
                "Connection error — notification service unreachable"
            )
            notification.save(update_fields=["status", "failure_reason", "updated_at"])

    except requests.exceptions.RequestException as e:
        logger.error("Notification service error for event %s: %s", event, str(e))
        if notification:
            notification.status = Notification.STATUS_FAILED
            notification.failure_reason = str(e)
            notification.save(update_fields=["status", "failure_reason", "updated_at"])

    return None


# ─────────────────────────────────────────────────────────────
# PUSH TOKEN MANAGEMENT
# These still go directly to external service
# (push tokens are device-level, not stored in our DB)
# ─────────────────────────────────────────────────────────────


def register_push_token(
    *, user_id: str, token: str, platform: str, device_id: str = None
):
    """
    Register an FCM push token for a device.
    Call this after login from the mobile/web client.

    platform: "android" | "ios" | "web"
    """
    if not settings.NOTIFICATION_API_KEY:
        logger.warning(
            "NOTIFICATION_API_KEY not set. Skipping push token registration."
        )
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
            f"{settings.NOTIFICATION_SERVICE_URL}/api/push-tokens/register",
            json=payload,
            headers=_headers(),
            timeout=10,
        )
        if not response.ok:
            logger.error(
                "Push token register failed %s: %s",
                response.status_code,
                response.text,
            )
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to register push token for user %s: %s", user_id, str(e))
    return None


def unregister_push_token(*, token: str):
    """
    Remove a push token. Call this on logout.
    """
    if not settings.NOTIFICATION_API_KEY:
        logger.warning(
            "NOTIFICATION_API_KEY not set. Skipping push token unregistration."
        )
        return None

    try:
        response = requests.post(
            f"{settings.NOTIFICATION_SERVICE_URL}/api/push-tokens/unregister",
            json={"token": token},
            headers=_headers(),
            timeout=10,
        )
        if not response.ok:
            logger.error(
                "Push token unregister failed %s: %s",
                response.status_code,
                response.text,
            )
            return None
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error("Failed to unregister push token: %s", str(e))
    return None
