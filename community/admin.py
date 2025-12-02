from django.contrib import admin
from django.utils.html import format_html
from .models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "post_count", "created_at"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}  # Auto-fill slug from name
    readonly_fields = ["created_at", "post_count"]
    ordering = ["name"]

    def post_count(self, obj):
        count = obj.posts.count()
        if count:
            url = f"/admin/community/post/?tags__id__exact={obj.id}"
            return format_html('<a href="{}">{} posts</a>', url, count)
        return "0"
    post_count.short_description = "Used in Posts"