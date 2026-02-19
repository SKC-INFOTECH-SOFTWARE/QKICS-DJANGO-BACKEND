from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Prefetch
from entrepreneurs.models import EntrepreneurProfile
from entrepreneurs.serializers import EntrepreneurProfileReadSerializer
from users.permissions import IsAdmin
from adminpanel.pagination import AdminPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction


class AdminEntrepreneurApplicationListView(ListAPIView):
    """
    Admin: List all entrepreneur applications.
    """

    queryset = EntrepreneurProfile.objects.select_related("user").all()
    serializer_class = EntrepreneurProfileReadSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [SearchFilter, OrderingFilter]

    search_fields = [
        "user__username",
        "user__email",
        "startup_name",
        "industry",
        "location",
    ]

    ordering_fields = [
        "application_status",
        "created_at",
        "funding_stage",
    ]


class AdminEntrepreneurApplicationUpdateView(APIView):
    """
    Admin approves or rejects entrepreneur application.
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
            return Response({"error": "Cannot modify superadmin"}, status=403)

        if profile.application_status != "pending":
            return Response(
                {"error": "Only pending applications can be processed"}, status=400
            )

        if action == "approve":

            if profile.user.user_type in ["expert", "investor"]:
                return Response(
                    {"error": "User already has another verified role"}, status=400
                )

            # Auto-reject expert application if exists
            if hasattr(profile.user, "expert_profile"):
                exp = profile.user.expert_profile
                exp.application_status = "rejected"
                exp.admin_review_note = "Auto-rejected: approved as Entrepreneur"
                exp.save()

            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "entrepreneur"
            profile.user.save()

        elif action == "reject":
            profile.verified_by_admin = False
            profile.application_status = "rejected"

        profile.admin_review_note = request.data.get("note", "")
        profile.save()

        return Response(
            {
                "message": f"Application {action}d successfully",
                "profile_id": profile.id,
                "new_status": profile.application_status,
            },
            status=200,
        )
