from django.utils import timezone
from subscriptions.models import UserSubscription


def get_active_subscription(user):
    """
    Returns the active subscription for a user, or None.
    """
    if not user or not user.is_authenticated:
        return None

    now = timezone.now()

    return (
        UserSubscription.objects.filter(
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


def is_user_premium_request(request):
    """
    Per-request memoised is_user_premium().

    Serializers ask this once per rendered object (twice, for content + is_locked),
    so a 10-post feed used to run ~20 identical UserSubscription queries. The answer
    cannot change within a single request, so resolve it once and hang it on the
    request.
    """
    user = getattr(request, "user", None) if request else None

    if not user or not user.is_authenticated:
        return False

    cached = getattr(request, "_premium_flag", None)
    if cached is not None and cached[0] == user.id:
        return cached[1]

    value = is_user_premium(user)
    try:
        request._premium_flag = (user.id, value)
    except AttributeError:
        pass  # not a real request object — just skip the memo
    return value


def remaining_premium_docs(user):
    """
    Returns remaining premium document downloads for this month.
    Counts from DocumentDownload records — the UserSubscription model
    does NOT have a premium_docs_used_this_month field.
    """
    from django.utils import timezone
    from documents.models import DocumentDownload

    sub = get_active_subscription(user)
    if not sub:
        return 0

    now = timezone.now()
    first_day_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    used_this_month = DocumentDownload.objects.filter(
        user=user,
        downloaded_at__gte=first_day_of_month,
        access_type_snapshot="PREMIUM",
    ).count()

    remaining = sub.plan.premium_doc_limit_per_month - used_this_month
    return max(0, remaining)


def can_use_free_consultation(user):
    """
    Premium users get one free consultation.
    """
    sub = get_active_subscription(user)
    if not sub:
        return False

    return not sub.free_consultation_used


def can_chat_with_expert(user):
    """
    Premium users can chat limited times per month.
    """
    sub = get_active_subscription(user)
    if not sub:
        return False

    return sub.chats_used_this_month < sub.plan.free_chat_per_month
