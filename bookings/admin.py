from django.contrib import admin
from .models import ExpertSlot, SlotRecurringPattern, Booking, BookingPayment, BookingReview

@admin.register(ExpertSlot)
class ExpertSlotAdmin(admin.ModelAdmin):
    list_display = ('id', 'expert', 'start_datetime', 'end_datetime', 'price', 'status')
    list_filter = ('status', 'requires_approval')
    search_fields = ('expert__email', 'expert__username')

@admin.register(SlotRecurringPattern)
class SlotRecurringPatternAdmin(admin.ModelAdmin):
    list_display = ('id', 'expert', 'weekday', 'start_time', 'end_time')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'expert', 'start_datetime', 'status', 'price')
    list_filter = ('status', )
    search_fields = ('user__email', 'expert__email')

@admin.register(BookingPayment)
class BookingPaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'user', 'amount', 'status', 'created_at')
    list_filter = ('status', 'gateway')

@admin.register(BookingReview)
class BookingReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'expert', 'rating', 'created_at')
    search_fields = ('expert__email', )
