# entrepreneurs/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import EntrepreneurProfile


@admin.register(EntrepreneurProfile)
class EntrepreneurProfileAdmin(admin.ModelAdmin):
    list_display = [
        "startup_name",
        "user_link",
        "safe_user_type",
        "funding_stage",
        "application_status",
        "verified_by_admin",
        "logo_preview",
        "created_at",
    ]
    list_filter = [
        "application_status",
        "verified_by_admin",
        "funding_stage",
        "created_at",
    ]
    search_fields = [
        "startup_name",
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "one_liner",
    ]
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at", "updated_at", "logo_preview"]
    ordering = ["-created_at"]

    fieldsets = (
        ("Startup", {
            "fields": ("user", "startup_name", "one_liner", "description", "website")
        }),
        ("Details", {
            "fields": ("industry", "location", "funding_stage")
        }),
        ("Media", {
            "fields": ("logo", "logo_preview")
        }),
        ("Verification", {
            "fields": ("application_status", "verified_by_admin"),
            "description": "Set to 'Approved' + check 'Verified' → appears in public directory"
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def user_link(self, obj):
        if not obj.user:
            return "— (Deleted User)"
        url = f"/admin/users/user/{obj.user.id}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = "User"

    def safe_user_type(self, obj):
        if not obj.user:
            return "—"
        return obj.user.get_user_type_display()
    safe_user_type.short_description = "Role"

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" style="max-height: 80px; border-radius: 8px;" />',
                obj.logo.url
            )
        return "—"
    logo_preview.short_description = "Logo"

    def save_model(self, request, obj, form, change):
        if obj.application_status == "approved" and obj.verified_by_admin:
            if obj.user and obj.user.user_type != "entrepreneur":
                obj.user.user_type = "entrepreneur"
                obj.user.save()
        super().save_model(request, obj, form, change)