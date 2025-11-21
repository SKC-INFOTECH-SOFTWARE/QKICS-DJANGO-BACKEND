from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from users.permissions import IsExpert, IsEntrepreneur
from .models import EntrepreneurProfile, ExpertProfile
from .serializers import EntrepreneurProfileSerializer, ExpertProfileSerializer
from rest_framework.permissions import AllowAny

# ────────────────────── ENTREPRENEUR PROFILE ──────────────────────
class EntrepreneurProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsEntrepreneur]

    def get(self, request):
        """Get logged-in user's entrepreneur profile"""
        try:
            profile = request.user.entrepreneur_profile
            serializer = EntrepreneurProfileSerializer(profile)
            return Response(serializer.data)
        except EntrepreneurProfile.DoesNotExist:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        """Create entrepreneur profile (only if verified)"""
        if request.user.user_type != "entrepreneur" or not request.user.is_verified:
            return Response(
                {"error": "Only verified entrepreneurs can create a profile."},
                status=status.HTTP_403_FORBIDDEN
            )
        if hasattr(request.user, "entrepreneur_profile"):
            return Response(
                {"error": "Profile already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = EntrepreneurProfileSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """Update own entrepreneur profile"""
        try:
            profile = request.user.entrepreneur_profile
        except EntrepreneurProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = EntrepreneurProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# ────────────────────── EXPERT PROFILE ──────────────────────
class ExpertProfileAPIView(APIView):
    permission_classes = [IsAuthenticated, IsExpert]

    def get(self, request):
        try:
            profile = request.user.expert_profile
            serializer = ExpertProfileSerializer(profile)
            return Response(serializer.data)
        except ExpertProfile.DoesNotExist:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        if request.user.user_type != "expert" or not request.user.is_verified:
            return Response(
                {"error": "Only verified experts can create a profile."},
                status=status.HTTP_403_FORBIDDEN
            )
        if hasattr(request.user, "expert_profile"):
            return Response(
                {"error": "Profile already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ExpertProfileSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        try:
            profile = request.user.expert_profile
        except ExpertProfile.DoesNotExist:
            return Response({"error": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ExpertProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ────────────────────── PUBLIC LISTINGS ──────────────────────
class VerifiedEntrepreneursListAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        profiles = EntrepreneurProfile.objects.select_related("user").all()
        serializer = EntrepreneurProfileSerializer(profiles, many=True)
        return Response(serializer.data)


class VerifiedExpertsListAPIView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        profiles = ExpertProfile.objects.select_related("user").filter(is_available=True)
        serializer = ExpertProfileSerializer(profiles, many=True)
        return Response(serializer.data)