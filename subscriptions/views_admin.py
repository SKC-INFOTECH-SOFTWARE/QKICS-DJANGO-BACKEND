from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Count, Q
from django.utils import timezone
from users.permissions import IsAdmin
from .models import SubscriptionPlan
from .serializers import SubscriptionPlanAdminSerializer


# =====================================================
# ADMIN: LIST + CREATE SUBSCRIPTION PLANS
# =====================================================
class AdminSubscriptionPlanListCreateView(generics.ListCreateAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanAdminSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    
    def get_queryset(self):
        now = timezone.now()

        return (
            SubscriptionPlan.objects
            .annotate(
                active_user_count=Count(
                    "user_subscriptions",
                    filter=Q(
                        user_subscriptions__is_active=True,
                        user_subscriptions__end_date__gt=now,
                    ),
                )
            )
        )

# =====================================================
# ADMIN: RETRIEVE + UPDATE + DELETE SUBSCRIPTION PLAN
# =====================================================
class AdminSubscriptionPlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanAdminSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_field = "uuid"
    
    def destroy(self, request, *args, **kwargs):
        """
        SOFT DELETE:
        - Marks plan as inactive instead of deleting
        """
        plan = self.get_object()

        if not plan.is_active:
            return Response(
                {"detail": "Subscription plan already inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        plan.is_active = False
        plan.save(update_fields=["is_active"])

        return Response(
            {"detail": "Subscription plan deactivated successfully"},
            status=status.HTTP_200_OK,
        )