from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "event",
        "title",
        "status",
        "is_read",
        "created_at",
    ]
    list_filter = [
        "status",
        "is_read",
        "event",
        "created_at",
    ]
    search_fields = [
        "user__username",
        "user__email",
        "event",
        "title",
    ]
    readonly_fields = [
        "uuid",
        "user",
        "event",
        "title",
        "body",
        "channels",
        "status",
        "data",
        "external_response",
        "failure_reason",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
