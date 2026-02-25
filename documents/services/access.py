from documents.models import Document
from subscriptions.services.access import is_user_premium


def can_user_download_document(user, document):
    """
    Master access control for document download.

    ONLY checks permission logic.
    Does NOT enforce usage limits.

    Returns:
        (bool, str) -> (allowed, reason)
    """

    if not document.is_active:
        return False, "Document is not available"

    if document.access_type == Document.AccessType.FREE:
        return True, "Free document"

    if document.access_type == Document.AccessType.PREMIUM:
        if not user or not user.is_authenticated:
            return False, "Login required"

        if not is_user_premium(user):
            return False, "Premium subscription required"

        return True, "Premium access granted"

    if document.access_type == Document.AccessType.PAID:
        return False, "Payment required (not enabled yet)"

    return False, "Access denied"