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
from django_filters.rest_framework import DjangoFilterBackend


class AdminExpertApplicationListView(ListAPIView):
    """
    Admin: List all expert applications.
    """

    queryset = ExpertProfile.objects.select_related("user").all()
    serializer_class = ExpertProfileReadSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = [
        "application_status",
        "verified_by_admin",
    ]

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
            return Response({"error": "Invalid action"}, status=400)

        if profile.user.user_type == "superadmin":
            return Response({"error": "Cannot modify superadmin"}, status=403)

        if action == "approve":
            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "expert"

        elif action == "reject":
            profile.verified_by_admin = False
            profile.application_status = "rejected"

            if profile.user.user_type == "expert":
                profile.user.user_type = "normal"

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
