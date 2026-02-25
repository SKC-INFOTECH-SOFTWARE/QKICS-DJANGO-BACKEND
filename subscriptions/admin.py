from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription


# ============================================================
# SUBSCRIPTION PLAN ADMIN
# ============================================================


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "price",
        "duration_days",
        "premium_doc_limit_per_month",
        "free_consultation_count",
        "free_chat_per_month",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "duration_days",
    )

    search_fields = ("name",)

    ordering = ("price",)


# ============================================================
# USER SUBSCRIPTION ADMIN
# ============================================================


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "start_date",
        "end_date",
        "is_active",
        "chats_used_this_month",
        "free_consultation_used",
        "created_at",
    )

    list_filter = (
        "is_active",
        "plan",
        "start_date",
        "end_date",
    )

    search_fields = (
        "user__email",
        "user__username",
    )

    readonly_fields = (
        "user",
        "plan",
        "start_date",
        "end_date",
        "created_at",
    )

    ordering = ("-created_at",)
