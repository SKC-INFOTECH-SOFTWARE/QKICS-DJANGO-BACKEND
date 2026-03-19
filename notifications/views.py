from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.generics import ListAPIView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Notification
from .serializers import NotificationSerializer
from .pagination import NotificationCursorPagination
from .services.client import register_push_token, unregister_push_token


class NotificationListView(ListAPIView):
    """
    GET /api/v1/notifications/

    Returns paginated notifications for the authenticated user from local DB.
    Most recent first.

    Query params:
        is_read     (optional) true / false — filter by read status
        cursor      (optional) — cursor for pagination
        page_size   (optional) — default 20, max 100
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationCursorPagination

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user)

        # Optional filter by read/unread
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            if is_read.lower() == "true":
                qs = qs.filter(is_read=True)
            elif is_read.lower() == "false":
                qs = qs.filter(is_read=False)

        return qs.order_by("-created_at")


class NotificationMarkReadView(APIView):
    """
    POST /api/v1/notifications/<uuid:notification_id>/read/

    Marks a single notification as read.
    Only works if the notification belongs to the authenticated user.
    Ownership is enforced — users cannot mark other users' notifications.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            uuid=notification_id,
            user=request.user,  # ownership check — critical
        )

        if notification.is_read:
            return Response(
                {"detail": "Notification is already marked as read."},
                status=status.HTTP_200_OK,
            )

        notification.mark_as_read()

        return Response(
            {
                "detail": "Notification marked as read.",
                "uuid": str(notification.uuid),
                "read_at": notification.read_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class NotificationMarkAllReadView(APIView):
    """
    POST /api/v1/notifications/read-all/

    Marks ALL unread notifications as read for the authenticated user.
    Returns count of notifications that were updated.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        now = timezone.now()

        updated_count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=now,
            status=Notification.STATUS_READ,
        )

        return Response(
            {
                "detail": f"{updated_count} notification(s) marked as read.",
                "updated_count": updated_count,
            },
            status=status.HTTP_200_OK,
        )


class UnreadNotificationCountView(APIView):
    """
    GET /api/v1/notifications/unread-count/

    Returns the count of unread notifications for the authenticated user.
    Useful for the notification bell badge on the frontend.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        return Response(
            {"unread_count": count},
            status=status.HTTP_200_OK,
        )


class NotificationDeleteView(APIView):
    """
    DELETE /api/v1/notifications/<uuid:notification_id>/

    Deletes a single notification.
    Only works if the notification belongs to the authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, notification_id):
        notification = get_object_or_404(
            Notification,
            uuid=notification_id,
            user=request.user,  # ownership check
        )

        notification.delete()

        return Response(
            {"detail": "Notification deleted."},
            status=status.HTTP_204_NO_CONTENT,
        )


class NotificationDeleteAllView(APIView):
    """
    DELETE /api/v1/notifications/delete-all/

    Deletes ALL notifications for the authenticated user.
    Optionally only delete read notifications using query param:
        ?only_read=true
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        qs = Notification.objects.filter(user=request.user)

        only_read = request.query_params.get("only_read", "false").lower()
        if only_read == "true":
            qs = qs.filter(is_read=True)

        deleted_count, _ = qs.delete()

        return Response(
            {
                "detail": f"{deleted_count} notification(s) deleted.",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────
# PUSH TOKEN MANAGEMENT
# ─────────────────────────────────────────────────────────────


class PushTokenRegisterView(APIView):
    """
    POST /api/v1/notifications/push-token/register/

    Register a device FCM token for the authenticated user.
    Call this after login from mobile/web client.

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
                {"detail": "Push token registration failed. Try again later."},
                status=status.HTTP_200_OK,
            )

        return Response(result, status=status.HTTP_200_OK)


class PushTokenUnregisterView(APIView):
    """
    POST /api/v1/notifications/push-token/unregister/

    Remove a push token from the notification service.
    Call this on logout so the device stops receiving push notifications.

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
                {"detail": "Push token unregister failed. Try again later."},
                status=status.HTTP_200_OK,
            )

        return Response(result, status=status.HTTP_200_OK)
