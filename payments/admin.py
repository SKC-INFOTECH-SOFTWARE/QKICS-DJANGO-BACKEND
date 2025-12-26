from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "user",
        "purpose",
        "amount",
        "status",
        "gateway",
        "created_at",
    )

    list_filter = (
        "purpose",
        "status",
        "gateway",
        "created_at",
    )

    search_fields = (
        "uuid",
        "user__email",
        "reference_id",
    )

    readonly_fields = (
        "uuid",
        "user",
        "purpose",
        "reference_id",
        "amount",
        "status",
        "gateway",
        "gateway_order_id",
        "gateway_payment_id",
        "gateway_response",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)
