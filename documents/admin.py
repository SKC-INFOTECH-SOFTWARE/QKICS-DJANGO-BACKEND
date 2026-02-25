from django.contrib import admin
from .models import Document, DocumentDownload


# =====================================================
# DOCUMENT ADMIN
# =====================================================
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "access_type",
        "is_active",
        "uploaded_by",
        "created_at",
    )

    list_filter = (
        "access_type",
        "is_active",
        "created_at",
    )

    search_fields = (
        "title",
        "description",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "uploaded_by",
    )

    ordering = ("-created_at",)

    fieldsets = (
        (
            "Document Info",
            {
                "fields": (
                    "title",
                    "description",
                    "file",
                )
            },
        ),
        (
            "Access Control",
            {
                "fields": (
                    "access_type",
                    "is_active",
                )
            },
        ),
        (
            "Audit Info",
            {
                "fields": (
                    "uploaded_by",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        """
        Automatically set uploaded_by to admin user.
        """
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


# =====================================================
# DOCUMENT DOWNLOAD HISTORY ADMIN
# =====================================================
@admin.register(DocumentDownload)
class DocumentDownloadAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "document",
        "access_type_snapshot",
        "downloaded_at",
    )

    list_filter = (
        "access_type_snapshot",
        "downloaded_at",
    )

    search_fields = (
        "user__username",
        "document__title",
    )

    readonly_fields = (
        "user",
        "document",
        "access_type_snapshot",
        "downloaded_at",
    )

    ordering = ("-downloaded_at",)

    def has_add_permission(self, request):
        """
        Prevent manual creation of download history.
        """
        return False

    def has_change_permission(self, request, obj=None):
        """
        Prevent editing download history.
        """
        return False
