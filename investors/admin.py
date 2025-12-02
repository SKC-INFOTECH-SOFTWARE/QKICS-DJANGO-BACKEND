from django.contrib import admin
from .models import Investor, Industry, StartupStage


@admin.register(Investor)
class InvestorAdmin(admin.ModelAdmin):
    list_display = ["display_name", "investor_type", "verified_by_admin", "application_status", "created_at"]
    list_filter = ["investor_type", "verified_by_admin", "application_status"]
    search_fields = ["display_name", "user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Profile", {"fields": ("user", "display_name", "one_liner", "investment_thesis")}),
        ("Investment Focus", {"fields": ("focus_industries", "preferred_stages", "investor_type")}),
        ("Ticket Size", {"fields": ("check_size_min", "check_size_max")}),
        ("Location & Links", {"fields": ("location", "website_url", "linkedin_url", "twitter_url")}),
        ("Admin", {"fields": ("verified_by_admin", "application_status", "created_by_admin", "is_active")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )


admin.site.register(Industry)
admin.site.register(StartupStage)