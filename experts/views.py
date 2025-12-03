from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    ExpertProfile,
    ExpertExperience,
    ExpertEducation,
    ExpertCertification,
    ExpertHonorAward,
)
from .serializers import (
    ExpertProfileReadSerializer,
    ExpertProfileWriteSerializer,
    ExperienceReadSerializer,
    ExperienceWriteSerializer,
    EducationReadSerializer,
    EducationWriteSerializer,
    CertificationReadSerializer,
    CertificationWriteSerializer,
    HonorAwardReadSerializer,
    HonorAwardWriteSerializer,
    ExpertApplicationSubmitSerializer,
    ExpertAdminVerifySerializer,
)
from django.contrib.auth import get_user_model
from users.permissions import IsAdmin

User = get_user_model()


# -----------------------
# Helpers
# -----------------------
def _is_profile_owner(request, expert_profile):
    return request.user.is_authenticated and expert_profile.user_id == request.user.id


def _is_expert_owner(request, expert_obj):
    # expert_obj is an instance of ExpertExperience, ExpertEducation, etc.
    return (
        request.user.is_authenticated
        and hasattr(request.user, "expert_profile")
        and expert_obj.expert.user_id == request.user.id
    )


# -----------------------
# Expert List (public): only approved/verified profiles
# -----------------------
class ExpertListView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        qs = ExpertProfile.objects.filter(verified_by_admin=True, application_status="approved").select_related("user")
        serializer = ExpertProfileReadSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


# -----------------------
# Expert Public Detail by username (no user id in URL)
# -----------------------
class ExpertDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request, username):
        user = get_object_or_404(User, username=username)
        profile = get_object_or_404(ExpertProfile.objects.select_related("user"), user=user, verified_by_admin=True)
        serializer = ExpertProfileReadSerializer(profile, context={"request": request})
        return Response(serializer.data)


# -----------------------
# Expert Self Profile (create / retrieve / update)
# -----------------------
class ExpertProfileSelfView(APIView):
    """
    POST: create profile for authenticated user (if not exists)
    GET: retrieve own profile
    PUT/PATCH: update own profile
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ExpertProfileReadSerializer(profile, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        if request.user.user_type in ["entrepreneur", "investor"]:
            return Response({
                "error": "You are already a verified entrepreneur or investor. Cannot create expert profile."
            }, status=400)

        if hasattr(request.user, "expert_profile"):
            return Response({"error": "Expert profile already exists"}, status=400)
        
        # create profile if not exists
        if hasattr(request.user, "expert_profile"):
            return Response({"detail": "Expert profile already exists."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ExpertProfileWriteSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            profile = serializer.save(user=request.user)
            # ensure OneToOne is honored; serializer.save should accept user kwarg
            read_ser = ExpertProfileReadSerializer(profile, context={"request": request})
            return Response(read_ser.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not _is_profile_owner(request, profile):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ExpertProfileWriteSerializer(profile, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(ExpertProfileReadSerializer(profile, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)

        if not _is_profile_owner(request, profile):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ExpertProfileWriteSerializer(profile, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(ExpertProfileReadSerializer(profile, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------
# Submit Application (expert requests review)
# -----------------------
class ExpertApplicationSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Create profile first before submitting."}, status=status.HTTP_400_BAD_REQUEST)

        if profile.application_status == "pending":
            return Response({"detail": "Application already pending."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ExpertApplicationSubmitSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(expert_profile=profile)
            return Response({"detail": "Application submitted."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -----------------------
# Admin verify/reject expert
# -----------------------
class AdminVerifyExpertView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, profile_id):
        profile = get_object_or_404(ExpertProfile.objects.select_related("user"), id=profile_id)
        serializer = ExpertAdminVerifySerializer(data=request.data, context={"request": request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        action = serializer.validated_data["action"]

        if action == "approve":
            # ←←← BLOCK IF USER ALREADY HAS ANOTHER VERIFIED ROLE ←←←
            if profile.user.user_type in ["entrepreneur", "investor"]:
                return Response({
                    "error": "User already has a verified role (entrepreneur/investor). Cannot approve as expert."
                }, status=400)

            # Auto-reject pending entrepreneur profile
            if hasattr(profile.user, "entrepreneur_profile"):
                ent = profile.user.entrepreneur_profile
                ent.application_status = "rejected"
                ent.admin_review_note = "Auto-rejected: approved as Expert"
                ent.save()

            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "expert"
            profile.user.save()
            profile.save()

            return Response({"message": "Expert approved. Other applications auto-rejected."})

        elif action == "reject":
            profile.application_status = "rejected"
            profile.save()
            return Response({"message": "Expert application rejected."})

        return Response({"error": "Invalid action"}, status=400)


# -----------------------
# Experience CRUD
# -----------------------
class ExperienceCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # user must have expert_profile
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Create expert profile first."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ExperienceWriteSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            exp = serializer.save(expert=profile)
            return Response(ExperienceReadSerializer(exp, context={"request": request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExperienceDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(ExpertExperience, pk=pk)

    def get(self, request, pk):
        exp = self.get_object(pk)
        return Response(ExperienceReadSerializer(exp, context={"request": request}).data)

    def put(self, request, pk):
        exp = self.get_object(pk)
        if not _is_expert_owner(request, exp):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ExperienceWriteSerializer(exp, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(ExperienceReadSerializer(exp, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        exp = self.get_object(pk)
        if not _is_expert_owner(request, exp):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        serializer = ExperienceWriteSerializer(exp, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(ExperienceReadSerializer(exp, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        exp = self.get_object(pk)
        if not _is_expert_owner(request, exp):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        exp.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# -----------------------
# Education CRUD
# -----------------------
class EducationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Create expert profile first."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = EducationWriteSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            edu = serializer.save(expert=profile)
            return Response(EducationReadSerializer(edu, context={"request": request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EducationDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(ExpertEducation, pk=pk)

    def get(self, request, pk):
        edu = self.get_object(pk)
        return Response(EducationReadSerializer(edu, context={"request": request}).data)

    def put(self, request, pk):
        edu = self.get_object(pk)
        if not _is_expert_owner(request, edu):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        serializer = EducationWriteSerializer(edu, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(EducationReadSerializer(edu, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        edu = self.get_object(pk)
        if not _is_expert_owner(request, edu):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        serializer = EducationWriteSerializer(edu, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(EducationReadSerializer(edu, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        edu = self.get_object(pk)
        if not _is_expert_owner(request, edu):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        edu.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# -----------------------
# Certification CRUD
# -----------------------
class CertificationCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Create expert profile first."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CertificationWriteSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            cert = serializer.save(expert=profile)
            return Response(CertificationReadSerializer(cert, context={"request": request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CertificationDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(ExpertCertification, pk=pk)

    def get(self, request, pk):
        cert = self.get_object(pk)
        return Response(CertificationReadSerializer(cert, context={"request": request}).data)

    def put(self, request, pk):
        cert = self.get_object(pk)
        if not _is_expert_owner(request, cert):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CertificationWriteSerializer(cert, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(CertificationReadSerializer(cert, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        cert = self.get_object(pk)
        if not _is_expert_owner(request, cert):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        serializer = CertificationWriteSerializer(cert, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(CertificationReadSerializer(cert, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        cert = self.get_object(pk)
        if not _is_expert_owner(request, cert):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        cert.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# -----------------------
# Honors & Awards CRUD
# -----------------------
class HonorAwardCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = getattr(request.user, "expert_profile", None)
        if not profile:
            return Response({"detail": "Create expert profile first."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = HonorAwardWriteSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            award = serializer.save(expert=profile)
            return Response(HonorAwardReadSerializer(award, context={"request": request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class HonorAwardDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_object(self, pk):
        return get_object_or_404(ExpertHonorAward, pk=pk)

    def get(self, request, pk):
        award = self.get_object(pk)
        return Response(HonorAwardReadSerializer(award, context={"request": request}).data)

    def put(self, request, pk):
        award = self.get_object(pk)
        if not _is_expert_owner(request, award):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        serializer = HonorAwardWriteSerializer(award, data=request.data, partial=False, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(HonorAwardReadSerializer(award, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        award = self.get_object(pk)
        if not _is_expert_owner(request, award):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        serializer = HonorAwardWriteSerializer(award, data=request.data, partial=True, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(HonorAwardReadSerializer(award, context={"request": request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        award = self.get_object(pk)
        if not _is_expert_owner(request, award):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        award.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
