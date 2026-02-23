from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404

from .models import EntrepreneurProfile
from .serializers import (
    EntrepreneurProfileReadSerializer,
    EntrepreneurProfileWriteSerializer,
    EntrepreneurApplicationSubmitSerializer,
    EntrepreneurAdminVerifySerializer,
)
from users.permissions import IsAdmin
from django.contrib.auth import get_user_model
from rest_framework.generics import ListAPIView
from .pagination import EntrepreneurCursorPagination

User = get_user_model()
from notifications.services.events import (
    notify_entrepreneur_application_approved,
    notify_entrepreneur_application_rejected,
)


# Public: List verified entrepreneurs
class EntrepreneurListView(ListAPIView):
    serializer_class = EntrepreneurProfileReadSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    pagination_class = EntrepreneurCursorPagination

    def get_queryset(self):
        return (
            EntrepreneurProfile.objects.filter(
                verified_by_admin=True, application_status="approved"
            )
            .select_related("user")
            .order_by("-created_at")
        )


# Public: Detail by username
class EntrepreneurDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        profile = get_object_or_404(
            EntrepreneurProfile, user=user, verified_by_admin=True
        )
        serializer = EntrepreneurProfileReadSerializer(
            profile, context={"request": request}
        )
        return Response(serializer.data)


# Self: Create / View / Update own profile
class EntrepreneurProfileSelfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "entrepreneur_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=404)
        serializer = EntrepreneurProfileReadSerializer(
            profile, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request):
        if request.user.user_type in ["expert", "investor"]:
            return Response(
                {
                    "error": "You are already a verified expert or investor. Cannot create entrepreneur profile."
                },
                status=400,
            )

        if hasattr(request.user, "entrepreneur_profile"):
            return Response(
                {"error": "Entrepreneur profile already exists"}, status=400
            )

        if hasattr(request.user, "entrepreneur_profile"):
            return Response({"detail": "Profile already exists."}, status=400)

        serializer = EntrepreneurProfileWriteSerializer(data=request.data)
        if serializer.is_valid():
            profile = serializer.save(user=request.user)
            return Response(
                EntrepreneurProfileReadSerializer(
                    profile, context={"request": request}
                ).data,
                status=201,
            )
        return Response(serializer.errors, status=400)

    def patch(self, request):
        profile = getattr(request.user, "entrepreneur_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=404)

        serializer = EntrepreneurProfileWriteSerializer(
            profile, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                EntrepreneurProfileReadSerializer(
                    profile, context={"request": request}
                ).data
            )
        return Response(serializer.errors, status=400)


# Submit for admin review
class EntrepreneurApplicationSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "entrepreneur_profile", None)
        if not profile:
            return Response({"detail": "Create profile first."}, status=400)
        if profile.application_status != "draft":
            return Response({"detail": "Application already submitted."}, status=400)

        serializer = EntrepreneurApplicationSubmitSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(profile=profile)
            return Response({"detail": "Application submitted successfully."})
        return Response(serializer.errors, status=400)


# Admin: Approve/Reject
class AdminVerifyEntrepreneurView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, profile_id):
        profile = get_object_or_404(
            EntrepreneurProfile.objects.select_related("user"), id=profile_id
        )
        serializer = EntrepreneurAdminVerifySerializer(
            data=request.data
        )  # Reuse same serializer

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        action = serializer.validated_data["action"]

        if action == "approve":
            # ←←← BLOCK IF USER ALREADY HAS ANOTHER VERIFIED ROLE ←←←
            if profile.user.user_type in ["expert", "investor"]:
                return Response(
                    {
                        "error": "User already has a verified role (expert/investor). Cannot approve as entrepreneur."
                    },
                    status=400,
                )

            # Auto-reject pending expert profile
            if hasattr(profile.user, "expert_profile"):
                exp = profile.user.expert_profile
                exp.application_status = "rejected"
                exp.admin_review_note = "Auto-rejected: approved as Entrepreneur"
                exp.save()

            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "entrepreneur"
            profile.user.save()
            profile.save()
            notify_entrepreneur_application_approved(profile)
            return Response(
                {"message": "Entrepreneur approved. Other applications auto-rejected."}
            )

        elif action == "reject":
            profile.application_status = "rejected"
            profile.save()
            notify_entrepreneur_application_rejected(profile)
            return Response({"message": "Entrepreneur application rejected."})

        return Response({"error": "Invalid action"}, status=400)
