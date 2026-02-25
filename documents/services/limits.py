from django.utils import timezone
from django.db import transaction

from documents.models import Document, DocumentDownload, DocumentPlatformSettings


def get_platform_settings():
    return DocumentPlatformSettings.objects.get_or_create(id=1)[0]


# =========================================================
# UPLOAD LIMIT
# =========================================================
def get_user_monthly_upload_limit(user):
    if user.is_superuser:
        return None

    if hasattr(user, "subscription") and user.subscription.is_active:
        return user.subscription.plan.monthly_upload_limit

    settings_obj = get_platform_settings()
    return settings_obj.monthly_upload_limit


def enforce_upload_limit(user):
    limit = get_user_monthly_upload_limit(user)

    if limit is None:
        return

    now = timezone.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    with transaction.atomic():
        monthly_count = (
            Document.objects.select_for_update()
            .filter(uploaded_by=user, created_at__gte=first_day)
            .count()
        )

        if monthly_count >= limit:
            raise Exception(f"Monthly upload limit ({limit}) reached.")


# =========================================================
# DOWNLOAD LIMIT
# =========================================================
def get_user_monthly_download_limit(user):
    if user.is_superuser:
        return None

    if hasattr(user, "subscription") and user.subscription.is_active:
        return user.subscription.plan.monthly_download_limit

    settings_obj = get_platform_settings()
    return settings_obj.monthly_download_limit


def enforce_download_limit(user):
    limit = get_user_monthly_download_limit(user)

    if limit is None:
        return

    now = timezone.now()
    first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_count = DocumentDownload.objects.filter(
        user=user,
        downloaded_at__gte=first_day,
    ).count()

    if monthly_count >= limit:
        raise Exception(f"Monthly download limit ({limit}) reached.")
