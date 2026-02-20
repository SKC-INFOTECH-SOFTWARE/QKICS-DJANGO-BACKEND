from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from .models import Investor, Industry, StartupStage
from .serializers import (
    InvestorReadSerializer,
    InvestorWriteSerializer,
    InvestorAdminVerifySerializer,
    IndustrySerializer,
    StartupStageSerializer,
)
from users.permissions import IsAdmin

User = get_user_model()


class AdminCreateInvestorProfileView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get("user_id")  # or username
        user = get_object_or_404(User, id=user_id)

        if hasattr(user, "investor_profile"):
            return Response({"error": "Investor profile already exists"}, status=400)

        serializer = InvestorWriteSerializer(data=request.data)
        if serializer.is_valid():
            investor = serializer.save(
                user=user,
                created_by_admin=request.user,
                verified_by_admin=True,
                application_status="approved",
                is_active=True,
            )
            return Response(
                {
                    "message": "Investor profile created and LIVE",
                    "investor_id": investor.id,
                    "display_name": investor.display_name,
                },
                status=201,
            )
        return Response(serializer.errors, status=400)


class InvestorProfileSelfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            investor = request.user.investor_profile
        except Investor.DoesNotExist:
            return Response({"detail": "Investor profile not found."}, status=404)

        serializer = InvestorReadSerializer(investor, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        try:
            investor = request.user.investor_profile
        except Investor.DoesNotExist:
            return Response({"detail": "Investor profile not found."}, status=404)

        serializer = InvestorWriteSerializer(investor, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                InvestorReadSerializer(investor, context={"request": request}).data
            )
        return Response(serializer.errors, status=400)


# Public: List all verified investors
class InvestorListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        investors = Investor.objects.filter(verified_by_admin=True, is_active=True)
        serializer = InvestorReadSerializer(
            investors, many=True, context={"request": request}
        )
        return Response(serializer.data)


# Public: Detail by username
class InvestorDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        investor = get_object_or_404(
            Investor, user=user, verified_by_admin=True, is_active=True
        )
        serializer = InvestorReadSerializer(investor, context={"request": request})
        return Response(serializer.data)


# Admin: Create investor (creates User + InvestorProfile)
class AdminCreateInvestorView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        data = request.data.copy()

        # Required fields
        username = data.pop("username", None)
        email = data.pop("email", None)
        password = data.pop("password", None)

        # Validation
        if not all([username, email, password]):
            return Response(
                {"error": "username, email, and password are required"}, status=400
            )

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken"}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already registered"}, status=400)

        # Create user with admin-defined password
        user = User.objects.create_user(
            username=username, email=email, password=password, user_type="investor"
        )

        # Create investor profile
        serializer = InvestorWriteSerializer(data=data)
        if serializer.is_valid():
            investor = serializer.save(
                user=user,
                created_by_admin=request.user,
                verified_by_admin=True,
                application_status="approved",
                is_active=True,
            )
            return Response(
                {
                    "message": "Investor created successfully",
                    "username": user.username,
                    "password_set_by_admin": True,
                    "investor_id": investor.id,
                },
                status=201,
            )

        # Rollback if profile fails
        user.delete()
        return Response(serializer.errors, status=400)


# Admin: Approve / Reject
class AdminVerifyInvestorView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request, investor_id):
        investor = get_object_or_404(Investor, id=investor_id)
        serializer = InvestorAdminVerifySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(investor)
            action = (
                "approved"
                if serializer.validated_data["action"] == "approve"
                else "rejected"
            )
            return Response({"detail": f"Investor {action}."})
        return Response(serializer.errors, status=400)


# Reference data
class IndustryListView(APIView):
    def get(self, request):
        return Response(IndustrySerializer(Industry.objects.all(), many=True).data)


class StartupStageListView(APIView):
    def get(self, request):
        return Response(
            StartupStageSerializer(StartupStage.objects.all(), many=True).data
        )
