from django.urls import path
from .views import (
    NotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    UnreadNotificationCountView,
    NotificationDeleteView,
    NotificationDeleteAllView,
    PushTokenRegisterView,
    PushTokenUnregisterView,
)

urlpatterns = [
    # ─────────────────────────────────────────
    # NOTIFICATION LIST
    # GET /api/v1/notifications/
    # Query params: is_read=true|false, cursor, page_size
    # ─────────────────────────────────────────
    path(
        "",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    # ─────────────────────────────────────────
    # UNREAD COUNT
    # GET /api/v1/notifications/unread-count/
    # Returns {"unread_count": N} for bell badge
    # ─────────────────────────────────────────
    path(
        "unread-count/",
        UnreadNotificationCountView.as_view(),
        name="notification-unread-count",
    ),
    # ─────────────────────────────────────────
    # MARK ALL AS READ
    # POST /api/v1/notifications/read-all/
    # ─────────────────────────────────────────
    path(
        "read-all/",
        NotificationMarkAllReadView.as_view(),
        name="notification-read-all",
    ),
    # ─────────────────────────────────────────
    # DELETE ALL
    # DELETE /api/v1/notifications/delete-all/
    # Optional query param: ?only_read=true
    # ─────────────────────────────────────────
    path(
        "delete-all/",
        NotificationDeleteAllView.as_view(),
        name="notification-delete-all",
    ),
    # ─────────────────────────────────────────
    # SINGLE NOTIFICATION — MARK READ
    # POST /api/v1/notifications/<uuid>/read/
    # ─────────────────────────────────────────
    path(
        "<uuid:notification_id>/read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    # ─────────────────────────────────────────
    # SINGLE NOTIFICATION — DELETE
    # DELETE /api/v1/notifications/<uuid>/
    # ─────────────────────────────────────────
    path(
        "<uuid:notification_id>/",
        NotificationDeleteView.as_view(),
        name="notification-delete",
    ),
    # ─────────────────────────────────────────
    # PUSH TOKEN MANAGEMENT
    # ─────────────────────────────────────────
    path(
        "push-token/register/",
        PushTokenRegisterView.as_view(),
        name="push-token-register",
    ),
    path(
        "push-token/unregister/",
        PushTokenUnregisterView.as_view(),
        name="push-token-unregister",
    ),
]
