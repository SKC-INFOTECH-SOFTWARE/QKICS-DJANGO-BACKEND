from django.contrib import admin

from .models import SystemLog


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "category", "logger_name", "short_message")
    list_filter = ("level", "category")
    search_fields = ("message", "logger_name", "detail")
    readonly_fields = ("level", "category", "logger_name", "message", "detail", "created_at")
    date_hierarchy = "created_at"

    def short_message(self, obj):
        return (obj.message or "")[:80]
    short_message.short_description = "Message"

    def has_add_permission(self, request):
        return False
