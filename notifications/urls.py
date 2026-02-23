from django.urls import path
from .views import (
    NotificationListView,
    NotificationMarkReadView,
    PushTokenRegisterView,
    PushTokenUnregisterView,
)

urlpatterns = [
    # List in-app notifications
    path(
        "",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    # Mark as read
    path(
        "<str:notification_id>/read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    # Push token management
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
