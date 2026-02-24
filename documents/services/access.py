from django.utils import timezone
from django.db.models import Count

from documents.models import Document, DocumentDownload
from subscriptions.services.access import is_user_premium
from documents.models import DocumentPlatformSettings



def can_user_download_document(user, document):
    """
    Master access check for document download.

    Returns:
        (bool, str) -> (allowed, reason)
    """

    # -------------------------------------------------
    # 1. Document must be active
    # -------------------------------------------------
    if not document.is_active:
        return False, "Document is not available"

    # -------------------------------------------------
    # 2. FREE documents
    # -------------------------------------------------
    if document.access_type == Document.AccessType.FREE:
        return True, "Free document"

    # -------------------------------------------------
    # 3. PREMIUM documents
    # -------------------------------------------------
    if document.access_type == Document.AccessType.PREMIUM:

        # Must be logged in
        if not user or not user.is_authenticated:
            return False, "Login required"

        # Must have active subscription
        if not is_user_premium(user):
            return False, "Premium subscription required"

        # Enforce monthly limit
        if not _can_download_more_this_month(user):
            return False, "Monthly premium download limit reached"

        return True, "Premium access granted"

    # -------------------------------------------------
    # 4. PAID documents (future)
    # -------------------------------------------------
    if document.access_type == Document.AccessType.PAID:
        return False, "Payment required (not enabled yet)"

    return False, "Access denied"



def _can_download_more_this_month(user):
    """
    Checks if user has remaining premium downloads for current month.
    """

    now = timezone.now()

    downloads_this_month = DocumentDownload.objects.filter(
        user=user,
        downloaded_at__year=now.year,
        downloaded_at__month=now.month,
        access_type_snapshot=Document.AccessType.PREMIUM,
    ).count()

    settings_obj, _ = DocumentPlatformSettings.objects.get_or_create(id=1)

    return downloads_this_month < settings_obj.monthly_download_limit
