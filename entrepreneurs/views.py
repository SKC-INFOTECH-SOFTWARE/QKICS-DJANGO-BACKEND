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

User = get_user_model()


# Public: List verified entrepreneurs
class EntrepreneurListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        profiles = EntrepreneurProfile.objects.filter(
            verified_by_admin=True, application_status="approved"
        )
        serializer = EntrepreneurProfileReadSerializer(profiles, many=True, context={"request": request})
        return Response(serializer.data)


# Public: Detail by username
class EntrepreneurDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        profile = get_object_or_404(
            EntrepreneurProfile, user=user, verified_by_admin=True
        )
        serializer = EntrepreneurProfileReadSerializer(profile, context={"request": request})
        return Response(serializer.data)


# Self: Create / View / Update own profile
class EntrepreneurProfileSelfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "entrepreneur_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=404)
        serializer = EntrepreneurProfileReadSerializer(profile, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        if hasattr(request.user, "entrepreneur_profile"):
            return Response({"detail": "Profile already exists."}, status=400)

        serializer = EntrepreneurProfileWriteSerializer(data=request.data)
        if serializer.is_valid():
            profile = serializer.save(user=request.user)
            return Response(
                EntrepreneurProfileReadSerializer(profile, context={"request": request}).data,
                status=201
            )
        return Response(serializer.errors, status=400)

    def patch(self, request):
        profile = getattr(request.user, "entrepreneur_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=404)

        serializer = EntrepreneurProfileWriteSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                EntrepreneurProfileReadSerializer(profile, context={"request": request}).data
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
            serializer.save(profile)
            return Response({"detail": "Application submitted successfully."})
        return Response(serializer.errors, status=400)


# Admin: Approve/Reject
class AdminVerifyEntrepreneurView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, profile_id):
        profile = get_object_or_404(EntrepreneurProfile, id=profile_id)
        serializer = EntrepreneurAdminVerifySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(profile)
            action = "approved" if serializer.validated_data["action"] == "approve" else "rejected"
            return Response({"detail": f"Profile {action}."})
        return Response(serializer.errors, status=400)