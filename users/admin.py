# users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "username",
        "email",
        "full_name",
        "user_type_display",
        "status",
        "profile_picture_preview",
        "is_staff",
        "date_joined",
    ]
    list_filter = [
        "user_type",
        "status",
        "is_staff",
        "is_active",
        "date_joined",
    ]
    search_fields = [
        "username",
        "email",
        "first_name",
        "last_name",
        "phone",
    ]
    ordering = ["-date_joined"]
    readonly_fields = [
        "date_joined",
        "last_login",
        "created_at",
        "updated_at",
        "profile_picture_preview",
    ]

    fieldsets = (
        ("Account", {
            "fields": ("username", "password")
        }),
        ("Personal Info", {
            "fields": ("first_name", "last_name", "email", "phone", "profile_picture", "profile_picture_preview")
        }),
        ("Role & Status", {
            "fields": ("user_type", "status", "is_active", "is_staff", "is_superuser")
        }),
        ("Important Dates", {
            "fields": ("last_login", "date_joined", "created_at", "updated_at")
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "user_type", "password1", "password2"),
        }),
    )

    def full_name(self, obj):
        return obj.get_full_name() or "—"
    full_name.short_description = "Full Name"

    def user_type_display(self, obj):
        return obj.get_user_type_display()
    user_type_display.short_description = "Role"

    def profile_picture_preview(self, obj):
        if obj.profile_picture:
            return format_html(
                '<img src="{}" style="width: 60px; height: 60px; object-fit: cover; border-radius: 50%;" />',
                obj.profile_picture.url
            )
        return "—"
    profile_picture_preview.short_description = "Photo"

    def has_delete_permission(self, request, obj=None):
        # Optional: Prevent deleting superadmin
        if obj and obj.user_type == "superadmin":
            return False
        return True