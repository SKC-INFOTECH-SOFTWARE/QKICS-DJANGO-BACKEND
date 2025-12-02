# experts/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import (
    ExpertProfile,
    ExpertExperience,
    ExpertEducation,
    ExpertCertification,
    ExpertHonorAward,
)


# Inlines
class ExpertExperienceInline(admin.TabularInline):
    model = ExpertExperience
    extra = 1
    fields = ["job_title", "company", "employment_type", "location", "start_date", "end_date"]


class ExpertEducationInline(admin.TabularInline):
    model = ExpertEducation
    extra = 1
    fields = ["school", "degree", "field_of_study", "start_year", "end_year"]


class ExpertCertificationInline(admin.TabularInline):
    model = ExpertCertification
    extra = 1
    fields = ["name", "issuing_organization", "issue_date", "expiration_date", "credential_id"]


class ExpertHonorAwardInline(admin.TabularInline):
    model = ExpertHonorAward
    extra = 1
    fields = ["title", "issuer", "issue_date"]


# FINAL — Only ONE registration with inlines
@admin.register(ExpertProfile)
class ExpertProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user_link",
        "full_name",
        "headline",
        "primary_expertise",
        "hourly_rate",
        "application_status",
        "verified_by_admin",
        "picture_preview",
        "created_at",
    ]
    list_filter = ["application_status", "verified_by_admin", "is_available", "created_at"]
    search_fields = ["user__username", "user__email", "headline", "primary_expertise"]
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at", "updated_at", "application_submitted_at", "picture_preview"]
    inlines = [
        ExpertExperienceInline,
        ExpertEducationInline,
        ExpertCertificationInline,
        ExpertHonorAwardInline,
    ]

    fieldsets = (
        ("User", {"fields": ("user",)}),
        ("Identity", {
            "fields": ("first_name", "last_name", "headline", "profile_picture", "picture_preview")
        }),
        ("Expertise", {"fields": ("primary_expertise", "other_expertise")}),
        ("Consultation", {"fields": ("hourly_rate", "is_available")}),
        ("Verification", {
            "fields": ("application_status", "verified_by_admin", "application_submitted_at", "admin_review_note")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def user_link(self, obj):
        url = reverse("admin:users_user_change", args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = "Username"

    def full_name(self, obj):
        return obj.user.get_full_name() or "—"
    full_name.short_description = "Name"

    def picture_preview(self, obj):
        if obj.profile_picture:
            return format_html('<img src="{}" style="max-height: 80px; border-radius: 50%;" />', obj.profile_picture.url)
        return "—"
    picture_preview.short_description = "Photo"

    def save_model(self, request, obj, form, change):
        if obj.application_status == "approved" and obj.verified_by_admin:
            if obj.user.user_type != "expert":
                obj.user.user_type = "expert"
                obj.user.save()
        super().save_model(request, obj, form, change)