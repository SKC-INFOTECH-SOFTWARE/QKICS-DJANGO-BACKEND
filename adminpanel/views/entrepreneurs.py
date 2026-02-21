from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from entrepreneurs.models import EntrepreneurProfile
from entrepreneurs.serializers import EntrepreneurProfileReadSerializer
from users.permissions import IsAdmin
from adminpanel.pagination import AdminPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction


# ============================================================
# ADMIN: LIST ENTREPRENEUR APPLICATIONS
# ============================================================


class AdminEntrepreneurApplicationListView(ListAPIView):
    """
    Admin: List all entrepreneur applications.
    Supports:
    - Filtering by status
    - Search
    - Ordering
    """

    queryset = EntrepreneurProfile.objects.select_related("user").filter(
        application_status__in=["pending", "approved", "rejected"]
    )
    serializer_class = EntrepreneurProfileReadSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    # Filtering
    filterset_fields = [
        "application_status",
        "verified_by_admin",
    ]

    # Search support
    search_fields = [
        "user__username",
        "user__email",
        "startup_name",
        "industry",
        "location",
    ]

    # Ordering support
    ordering_fields = [
        "application_status",
        "created_at",
        "funding_stage",
    ]

    ordering = ["-created_at"]


# ============================================================
# ADMIN: APPROVE / REJECT ENTREPRENEUR
# ============================================================


class AdminEntrepreneurApplicationUpdateView(APIView):
    """
    Admin can approve or reject entrepreneur application.
    Admin has full override power.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def patch(self, request, profile_id):

        profile = get_object_or_404(
            EntrepreneurProfile.objects.select_related("user"), id=profile_id
        )

        action = request.data.get("action")

        if action not in ["approve", "reject"]:
            return Response(
                {"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Prevent modifying superadmin
        if profile.user.user_type == "superadmin":
            return Response(
                {"error": "Cannot modify superadmin"}, status=status.HTTP_403_FORBIDDEN
            )

        # ============================
        # APPROVE
        # ============================
        if action == "approve":

            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "entrepreneur"

        # ============================
        # REJECT
        # ============================
        elif action == "reject":

            profile.verified_by_admin = False
            profile.application_status = "rejected"

            # If currently entrepreneur → downgrade to normal
            if profile.user.user_type == "entrepreneur":
                profile.user.user_type = "normal"

        # Save changes
        profile.user.save()
        profile.admin_review_note = request.data.get("note", "")
        profile.save()

        return Response(
            {
                "message": f"Application {action}d successfully",
                "profile_id": profile.id,
                "new_status": profile.application_status,
            },
            status=status.HTTP_200_OK,
        )
