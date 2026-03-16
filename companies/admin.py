from django.contrib import admin
from .models import CompanyPostSettings


@admin.register(CompanyPostSettings)
class CompanyPostSettingsAdmin(admin.ModelAdmin):
    list_display = ("free_posts_per_company", "paid_post_price", "updated_at")