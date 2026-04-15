from django.contrib import admin
from django.utils.html import format_html
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'uuid', 'user', 'purpose', 'amount',
        'status_badge', 'gateway', 'reference_id', 'created_at',
    )
    list_filter = ('purpose', 'status', 'gateway', 'created_at')
    search_fields = (
        'uuid', 'user__username', 'user__email',
        'reference_id', 'gateway_order_id', 'gateway_payment_id',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    # uuid is system-generated; reference_id and timestamps are audit fields
    readonly_fields = (
        'uuid', 'reference_id', 'created_at', 'updated_at',
    )

    fieldsets = (
        ('Payment Details', {
            'fields': ('user', 'purpose', 'reference_id', 'amount'),
        }),
        ('Status & Gateway', {
            'fields': (
                'status', 'gateway',
                'gateway_order_id', 'gateway_payment_id',
                'gateway_response',
            ),
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['mark_success', 'mark_failed']

    def status_badge(self, obj):
        colors = {
            Payment.STATUS_INITIATED: ('orange',  '⏳ INITIATED'),
            Payment.STATUS_SUCCESS:   ('green',   '✔ SUCCESS'),
            Payment.STATUS_FAILED:    ('red',     '✘ FAILED'),
        }
        color, label = colors.get(obj.status, ('black', obj.status))
        return format_html(
            '<span style="color:{};font-weight:bold;">{}</span>', color, label
        )
    status_badge.short_description = 'Status'

    @admin.action(description='Mark selected payments as SUCCESS')
    def mark_success(self, request, queryset):
        updated = queryset.filter(
            status=Payment.STATUS_INITIATED
        ).update(status=Payment.STATUS_SUCCESS)
        self.message_user(request, f'{updated} payment(s) marked as SUCCESS.')

    @admin.action(description='Mark selected payments as FAILED')
    def mark_failed(self, request, queryset):
        updated = queryset.filter(
            status=Payment.STATUS_INITIATED
        ).update(status=Payment.STATUS_FAILED)
        self.message_user(request, f'{updated} payment(s) marked as FAILED.')