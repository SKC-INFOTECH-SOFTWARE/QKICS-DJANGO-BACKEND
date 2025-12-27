from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription


# ============================================================
# SUBSCRIPTION PLAN SERIALIZER
# ============================================================


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for subscription plans.
    """

    class Meta:
        model = SubscriptionPlan
        fields = [
            "uuid",
            "name",
            "price",
            "duration_days",
            "premium_doc_limit_per_month",
            "free_consultation_count",
            "free_chat_per_month",
            "is_active",
        ]
        read_only_fields = fields


# ============================================================
# USER SUBSCRIPTION SERIALIZER
# ============================================================


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for user's active subscription.
    """

    plan = SubscriptionPlanSerializer(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            "plan",
            "start_date",
            "end_date",
            "is_active",
            "premium_docs_used_this_month",
            "chats_used_this_month",
            "free_consultation_used",
            "created_at",
        ]
        read_only_fields = fields
