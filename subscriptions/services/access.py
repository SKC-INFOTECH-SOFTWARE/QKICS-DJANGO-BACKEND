from django.utils import timezone
from subscriptions.models import UserSubscription


# ============================================================
# CORE HELPERS
# ============================================================

def get_active_subscription(user):
    """
    Returns the active subscription for a user, or None.
    """
    if not user or not user.is_authenticated:
        return None

    now = timezone.now()

    return (
        UserSubscription.objects
        .filter(
            user=user,
            is_active=True,
            start_date__lte=now,
            end_date__gt=now,
        )
        .order_by("-created_at")
        .first()
    )


def is_user_premium(user):
    """
    True if user has an active subscription.
    """
    return get_active_subscription(user) is not None


# ============================================================
# DOCUMENT ACCESS
# ============================================================

def can_download_premium_doc(user):
    """
    Check if user can download a premium document.
    """
    sub = get_active_subscription(user)
    if not sub:
        return False

    return (
        sub.premium_docs_used_this_month
        < sub.plan.premium_doc_limit_per_month
    )


def remaining_premium_docs(user):
    """
    Returns remaining premium document downloads for the month.
    """
    sub = get_active_subscription(user)
    if not sub:
        return 0

    remaining = (
        sub.plan.premium_doc_limit_per_month
        - sub.premium_docs_used_this_month
    )
    return max(0, remaining)


# ============================================================
# CONSULTATION BENEFITS
# ============================================================

def can_use_free_consultation(user):
    """
    Premium users get one free consultation.
    """
    sub = get_active_subscription(user)
    if not sub:
        return False

    return not sub.free_consultation_used


# ============================================================
# CHAT BENEFITS
# ============================================================

def can_chat_with_expert(user):
    """
    Premium users can chat limited times per month.
    """
    sub = get_active_subscription(user)
    if not sub:
        return False

    return (
        sub.chats_used_this_month
        < sub.plan.free_chat_per_month
    )
