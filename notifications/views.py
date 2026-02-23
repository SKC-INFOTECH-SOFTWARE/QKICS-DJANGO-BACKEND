from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .services.client import (
    get_notifications,
    mark_notification_read,
    register_push_token,
    unregister_push_token,
)


class NotificationListView(APIView):
    """
    GET /api/v1/notifications/
    Returns in-app notifications for the authenticated user.

    Query params:
      channel  (default: IN_APP)
      limit    (default: 20)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        channel = request.query_params.get("channel", "IN_APP")
        limit = int(request.query_params.get("limit", 20))

        result = get_notifications(
            user_id=request.user.id,
            channel=channel,
            limit=limit,
        )

        if result is None:
            return Response(
                {"detail": "Notification service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    """
    POST /api/v1/notifications/<notification_id>/read/
    Marks a single in-app notification as read.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        result = mark_notification_read(notification_id=notification_id)

        if result is None:
            return Response(
                {"detail": "Notification service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result, status=status.HTTP_200_OK)


class PushTokenRegisterView(APIView):
    """
    POST /api/v1/notifications/push-token/register/
    Register a device FCM token for the authenticated user.

    Body:
      token      (str, required)  — FCM token
      platform   (str, required)  — "android" | "ios" | "web"
      deviceId   (str, optional)  — unique device identifier
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")
        platform = request.data.get("platform")
        device_id = request.data.get("deviceId")

        if not token or not platform:
            return Response(
                {"detail": "token and platform are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if platform not in ("android", "ios", "web"):
            return Response(
                {"detail": "platform must be one of: android, ios, web."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = register_push_token(
            user_id=request.user.id,
            token=token,
            platform=platform,
            device_id=device_id,
        )

        if result is None:
            return Response(
                {"detail": "Notification service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result, status=status.HTTP_200_OK)


class PushTokenUnregisterView(APIView):
    """
    POST /api/v1/notifications/push-token/unregister/
    Remove a push token (call on logout).

    Body:
      token  (str, required)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("token")

        if not token:
            return Response(
                {"detail": "token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = unregister_push_token(token=token)

        if result is None:
            return Response(
                {"detail": "Notification service unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(result, status=status.HTTP_200_OK)
