from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import Payment
from payments.services.fake import FakePaymentService

from subscriptions.models import SubscriptionPlan, UserSubscription
from subscriptions.serializers import (
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
)
from subscriptions.services.access import get_active_subscription
from notifications.services.events import notify_subscription_activated

class SubscriptionPlanListView(generics.ListAPIView):
    """
    Public API to list all active subscription plans.

    - Anyone can view plans (login not required)
    - Only active plans are returned
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = SubscriptionPlanSerializer

    def get_queryset(self):
        return SubscriptionPlan.objects.filter(is_active=True)


class SubscribeView(APIView):
    """
    Subscribe the logged-in user to a subscription plan.

    Flow:
    1. Validate plan
    2. Prevent multiple active subscriptions
    3. Create fake payment
    4. Confirm payment
    5. Create UserSubscription
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        plan_uuid = request.data.get("plan_uuid")

        # -----------------------------
        # Validate input
        # -----------------------------
        if not plan_uuid:
            return Response(
                {"detail": "plan_uuid is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------
        # Fetch subscription plan
        # -----------------------------
        try:
            plan = SubscriptionPlan.objects.get(
                uuid=plan_uuid,
                is_active=True,
            )
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"detail": "Invalid subscription plan"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # -----------------------------
        # Prevent multiple active subscriptions
        # -----------------------------
        if UserSubscription.objects.filter(
            user=request.user,
            is_active=True,
            end_date__gt=timezone.now(),
        ).exists():
            return Response(
                {"detail": "You already have an active subscription"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------
        # Step 1: Fake payment
        # -----------------------------
        payment_service = FakePaymentService()

        payment = payment_service.create_payment(
            user=request.user,
            purpose=Payment.PURPOSE_SUBSCRIPTION,
            reference_id=plan.uuid,
            amount=plan.price,
        )

        # Confirm payment immediately (fake)
        payment_service.confirm_payment(payment=payment)

        # -----------------------------
        # Step 2: Create subscription
        # -----------------------------
        start_date = timezone.now()
        end_date = start_date + timedelta(days=plan.duration_days)

        subscription = UserSubscription.objects.create(
            user=request.user,
            plan=plan,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )
        notify_subscription_activated(subscription)
        return Response(
            UserSubscriptionSerializer(subscription).data,
            status=status.HTTP_201_CREATED,
        )


class MySubscriptionView(APIView):
    """
    Returns the logged-in user's active subscription.

    - 404 if no active subscription
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        subscription = get_active_subscription(request.user)

        if not subscription:
            return Response(
                {"detail": "No active subscription"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            UserSubscriptionSerializer(subscription).data,
            status=status.HTTP_200_OK,
        )
