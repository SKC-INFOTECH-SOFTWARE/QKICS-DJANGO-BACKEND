from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from django.urls import reverse

from payments.models import Payment
from payments.services.factory import get_payment_service
from payments.services.dispatch import fulfill_payment

from subscriptions.models import SubscriptionPlan, UserSubscription
from subscriptions.serializers import (
    SubscriptionPlanSerializer,
    UserSubscriptionSerializer,
)
from subscriptions.services.access import get_active_subscription


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
                {"message": "plan_uuid is required"},
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
                {"message": "Invalid subscription plan"},
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
                {"message": "You already have an active subscription"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------
        # Step 1: Start payment via the configured gateway
        # -----------------------------
        service = get_payment_service()

        payment = service.create_payment(
            user=request.user,
            purpose=Payment.PURPOSE_SUBSCRIPTION,
            reference_id=plan.uuid,
            amount=plan.price,
        )

        surl = request.build_absolute_uri(reverse("payu-callback-success"))
        furl = request.build_absolute_uri(reverse("payu-callback-failure"))
        instruction = service.start_checkout(
            payment=payment,
            customer={
                "name": (request.user.get_full_name() or request.user.username or "Customer"),
                "email": request.user.email or "",
                "phone": getattr(request.user, "phone", "") or "",
            },
            surl=surl,
            furl=furl,
        )

        # -----------------------------
        # Instant gateways (fake): confirm + activate right away.
        # -----------------------------
        if instruction.get("flow") == "instant":
            service.confirm_payment(payment=payment)
            fulfill_payment(payment)
            subscription = (
                UserSubscription.objects.filter(user=request.user, is_active=True)
                .order_by("-created_at")
                .first()
            )
            return Response(
                UserSubscriptionSerializer(subscription).data,
                status=status.HTTP_201_CREATED,
            )

        # -----------------------------
        # Hosted checkout (payu): return redirect params for the client.
        # -----------------------------
        return Response(
            {
                "flow": instruction["flow"],
                "payment_uuid": str(payment.uuid),
                "checkout": {
                    "action_url": instruction["action_url"],
                    "params": instruction["params"],
                },
            },
            status=status.HTTP_200_OK,
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
                {"message": "No active subscription"},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            UserSubscriptionSerializer(subscription).data,
            status=status.HTTP_200_OK,
        )
