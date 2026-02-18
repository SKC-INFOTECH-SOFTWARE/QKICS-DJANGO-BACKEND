from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from experts.models import ExpertProfile
from experts.serializers import ExpertProfileReadSerializer
from users.permissions import IsAdmin
from adminpanel.pagination import AdminPagination
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction


class AdminExpertApplicationListView(ListAPIView):
    """
    Admin: List all expert applications.
    """

    queryset = ExpertProfile.objects.select_related("user").all()
    serializer_class = ExpertProfileReadSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [SearchFilter, OrderingFilter]

    search_fields = [
        "user__username",
        "user__email",
        "primary_expertise",
    ]

    ordering_fields = [
        "application_submitted_at",
        "created_at",
        "application_status",
    ]


class AdminExpertApplicationUpdateView(APIView):
    """
    Admin approves or rejects expert application.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    @transaction.atomic
    def patch(self, request, profile_id):
        profile = get_object_or_404(
            ExpertProfile.objects.select_related("user"), id=profile_id
        )

        action = request.data.get("action")

        if action not in ["approve", "reject"]:
            return Response(
                {"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Prevent non-superadmin modifying superadmin
        if profile.user.user_type == "superadmin":
            return Response({"error": "Cannot modify superadmin"}, status=403)

        if action == "approve":

            if profile.application_status != "pending":
                return Response(
                    {"error": "Only pending applications can be approved"}, status=400
                )

            if profile.user.user_type in ["entrepreneur", "investor"]:
                return Response(
                    {"error": "User already has another verified role"}, status=400
                )

            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "expert"
            profile.user.save()

        elif action == "reject":

            if profile.application_status != "pending":
                return Response(
                    {"error": "Only pending applications can be rejected"}, status=400
                )

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
