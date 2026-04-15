from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import ExpertSlot, SlotRecurringPattern, Booking, InvestorSlot, InvestorBooking


# ─────────────────────────────────────────────
# EXPERT SLOT
# ─────────────────────────────────────────────

@admin.register(ExpertSlot)
class ExpertSlotAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'expert', 'start_datetime', 'end_datetime',
        'duration_minutes', 'price', 'status', 'requires_approval',
        'is_recurring', 'availability_badge', 'created_at',
    )
    list_filter = ('status', 'requires_approval', 'is_recurring', 'created_at')
    search_fields = ('expert__username', 'expert__email')
    ordering = ('-start_datetime',)
    date_hierarchy = 'start_datetime'

    readonly_fields = ('uuid', 'created_at', 'updated_at')

    fieldsets = (
        ('Expert & Timing', {
            'fields': ('expert', 'start_datetime', 'end_datetime', 'duration_minutes'),
        }),
        ('Pricing & Settings', {
            'fields': ('price', 'requires_approval', 'is_recurring', 'status'),
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['mark_active', 'mark_disabled']

    def availability_badge(self, obj):
        if obj.is_available():
            return format_html('<span style="color:green;font-weight:bold;">✔ Available</span>')
        return format_html('<span style="color:red;">✘ Unavailable</span>')
    availability_badge.short_description = 'Available?'

    @admin.action(description='Mark selected slots as ACTIVE')
    def mark_active(self, request, queryset):
        updated = queryset.update(status='ACTIVE')
        self.message_user(request, f'{updated} slot(s) marked ACTIVE.')

    @admin.action(description='Mark selected slots as DISABLED')
    def mark_disabled(self, request, queryset):
        updated = queryset.update(status='DISABLED')
        self.message_user(request, f'{updated} slot(s) marked DISABLED.')


# ─────────────────────────────────────────────
# SLOT RECURRING PATTERN
# ─────────────────────────────────────────────

@admin.register(SlotRecurringPattern)
class SlotRecurringPatternAdmin(admin.ModelAdmin):
    WEEKDAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    list_display = (
        'id', 'expert', 'weekday_name', 'start_time', 'end_time',
        'start_date', 'end_date', 'is_active', 'created_at',
    )
    list_filter = ('is_active', 'weekday', 'start_date')
    search_fields = ('expert__username', 'expert__email')
    ordering = ('expert', 'weekday', 'start_time')

    readonly_fields = ('uuid', 'created_at', 'updated_at')

    fieldsets = (
        ('Expert', {'fields': ('expert',)}),
        ('Schedule', {
            'fields': ('weekday', 'start_time', 'end_time', 'start_date', 'end_date'),
        }),
        ('Status', {'fields': ('is_active',)}),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def weekday_name(self, obj):
        return self.WEEKDAY_NAMES[obj.weekday] if 0 <= obj.weekday <= 6 else obj.weekday
    weekday_name.short_description = 'Day'


# ─────────────────────────────────────────────
# BOOKING
# ─────────────────────────────────────────────

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'expert', 'start_datetime', 'duration_minutes',
        'price', 'status_badge', 'requires_expert_approval',
        'paid_at', 'created_at',
    )
    list_filter = ('status', 'requires_expert_approval', 'created_at', 'start_datetime')
    search_fields = (
        'user__username', 'user__email',
        'expert__username', 'expert__email',
        'uuid', 'payment_intent_id',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    readonly_fields = (
        'uuid', 'platform_fee_amount', 'expert_earning_amount',
        'created_at', 'updated_at',
    )

    fieldsets = (
        ('Participants', {
            'fields': ('user', 'expert', 'slot'),
        }),
        ('Session Details', {
            'fields': (
                'start_datetime', 'end_datetime', 'duration_minutes',
                'chat_room_id',
            ),
        }),
        ('Status & Approval', {
            'fields': (
                'status', 'requires_expert_approval',
                'expert_approved_at', 'paid_at', 'confirmed_at',
                'completed_at', 'declined_at', 'cancelled_at', 'expired_at',
            ),
        }),
        ('Financials', {
            'fields': (
                'price', 'platform_fee_percent',
                'platform_fee_amount', 'expert_earning_amount',
                'payment_intent_id',
            ),
        }),
        ('Reasons', {
            'fields': ('cancellation_reason', 'decline_reason'),
            'classes': ('collapse',),
        }),
        ('System', {
            'fields': ('uuid', 'reschedule_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = [
        'mark_confirmed', 'mark_completed',
        'mark_cancelled', 'mark_expired',
    ]

    def status_badge(self, obj):
        colors = {
            'PENDING':           ('orange',  '⏳'),
            'AWAITING_PAYMENT':  ('#d97706', '💳'),
            'PAID':              ('blue',    '💰'),
            'CONFIRMED':         ('green',   '✔'),
            'COMPLETED':         ('#065f46', '🏁'),
            'DECLINED':          ('red',     '✘'),
            'CANCELLED':         ('gray',    '✘'),
            'FAILED':            ('darkred', '✘'),
            'EXPIRED':           ('#6b7280', '⌛'),
        }
        color, icon = colors.get(obj.status, ('black', '?'))
        return format_html(
            '<span style="color:{};font-weight:bold;">{} {}</span>',
            color, icon, obj.status,
        )
    status_badge.short_description = 'Status'

    @admin.action(description='Mark selected bookings as CONFIRMED')
    def mark_confirmed(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(
            status__in=['PENDING', 'AWAITING_PAYMENT', 'PAID']
        ).update(status='CONFIRMED', confirmed_at=now)
        self.message_user(request, f'{updated} booking(s) confirmed.')

    @admin.action(description='Mark selected bookings as COMPLETED')
    def mark_completed(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(status='CONFIRMED').update(
            status='COMPLETED', completed_at=now
        )
        self.message_user(request, f'{updated} booking(s) completed.')

    @admin.action(description='Mark selected bookings as CANCELLED')
    def mark_cancelled(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(
            status__in=['PENDING', 'AWAITING_PAYMENT', 'PAID', 'CONFIRMED']
        ).update(status='CANCELLED', cancelled_at=now)
        self.message_user(request, f'{updated} booking(s) cancelled.')

    @admin.action(description='Mark selected bookings as EXPIRED')
    def mark_expired(self, request, queryset):
        now = timezone.now()
        updated = queryset.filter(
            status__in=['PENDING', 'AWAITING_PAYMENT']
        ).update(status='EXPIRED', expired_at=now)
        self.message_user(request, f'{updated} booking(s) expired.')


# ─────────────────────────────────────────────
# INVESTOR SLOT
# ─────────────────────────────────────────────

@admin.register(InvestorSlot)
class InvestorSlotAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'investor', 'start_datetime', 'end_datetime',
        'duration_minutes', 'status', 'availability_badge', 'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('investor__username', 'investor__email')
    ordering = ('-start_datetime',)
    date_hierarchy = 'start_datetime'

    readonly_fields = ('uuid', 'created_at', 'updated_at')

    fieldsets = (
        ('Investor & Timing', {
            'fields': ('investor', 'start_datetime', 'end_datetime', 'duration_minutes'),
        }),
        ('Status', {'fields': ('status',)}),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['mark_active', 'mark_disabled']

    def availability_badge(self, obj):
        if obj.is_available():
            return format_html('<span style="color:green;font-weight:bold;">✔ Available</span>')
        return format_html('<span style="color:red;">✘ Unavailable</span>')
    availability_badge.short_description = 'Available?'

    @admin.action(description='Mark selected slots as ACTIVE')
    def mark_active(self, request, queryset):
        updated = queryset.update(status='ACTIVE')
        self.message_user(request, f'{updated} investor slot(s) marked ACTIVE.')

    @admin.action(description='Mark selected slots as DISABLED')
    def mark_disabled(self, request, queryset):
        updated = queryset.update(status='DISABLED')
        self.message_user(request, f'{updated} investor slot(s) marked DISABLED.')


# ─────────────────────────────────────────────
# INVESTOR BOOKING
# ─────────────────────────────────────────────

@admin.register(InvestorBooking)
class InvestorBookingAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'investor', 'start_datetime',
        'duration_minutes', 'status_badge', 'reschedule_count', 'created_at',
    )
    list_filter = ('status', 'created_at', 'start_datetime')
    search_fields = (
        'user__username', 'user__email',
        'investor__username', 'investor__email',
        'uuid',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    readonly_fields = ('uuid', 'created_at', 'updated_at')

    fieldsets = (
        ('Participants', {
            'fields': ('user', 'investor', 'slot'),
        }),
        ('Session Details', {
            'fields': (
                'start_datetime', 'end_datetime',
                'duration_minutes', 'chat_room_id',
            ),
        }),
        ('Status', {
            'fields': ('status', 'reschedule_count'),
        }),
        ('System', {
            'fields': ('uuid', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['mark_confirmed', 'mark_completed', 'mark_cancelled']

    def status_badge(self, obj):
        colors = {
            'PENDING':      ('orange', '⏳'),
            'CONFIRMED':    ('green',  '✔'),
            'CANCELLED':    ('gray',   '✘'),
            'RESCHEDULED':  ('blue',   '🔄'),
            'COMPLETED':    ('#065f46', '🏁'),
        }
        color, icon = colors.get(obj.status, ('black', '?'))
        return format_html(
            '<span style="color:{};font-weight:bold;">{} {}</span>',
            color, icon, obj.status,
        )
    status_badge.short_description = 'Status'

    @admin.action(description='Mark selected bookings as CONFIRMED')
    def mark_confirmed(self, request, queryset):
        updated = queryset.filter(status='PENDING').update(status='CONFIRMED')
        self.message_user(request, f'{updated} investor booking(s) confirmed.')

    @admin.action(description='Mark selected bookings as COMPLETED')
    def mark_completed(self, request, queryset):
        updated = queryset.filter(status='CONFIRMED').update(status='COMPLETED')
        self.message_user(request, f'{updated} investor booking(s) completed.')

    @admin.action(description='Mark selected bookings as CANCELLED')
    def mark_cancelled(self, request, queryset):
        updated = queryset.filter(
            status__in=['PENDING', 'CONFIRMED']
        ).update(status='CANCELLED')
        self.message_user(request, f'{updated} investor booking(s) cancelled.')