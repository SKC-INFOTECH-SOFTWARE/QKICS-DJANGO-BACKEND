from rest_framework import serializers
from django.utils import timezone

from .models import (
    ExpertProfile,
    ExpertExperience,
    ExpertEducation,
    ExpertCertification,
    ExpertHonorAward,
)
from django.contrib.auth import get_user_model

User = get_user_model()


# ======================================================
# BASIC USER SERIALIZER FOR PUBLIC EXPERT VIEW
# ======================================================
class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "uuid", "username", "profile_picture"]


# ======================================================
# NESTED READ-ONLY SERIALIZERS
# (Used for public expert detail & expert self-dashboard)
# ======================================================


class ExperienceReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertExperience
        fields = [
            "id",
            "job_title",
            "company",
            "employment_type",
            "location",
            "start_date",
            "end_date",
            "description",
        ]


class EducationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertEducation
        fields = [
            "id",
            "school",
            "degree",
            "field_of_study",
            "start_year",
            "end_year",
            "grade",
            "description",
        ]


class CertificationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertCertification
        fields = [
            "id",
            "name",
            "issuing_organization",
            "issue_date",
            "expiration_date",
            "credential_id",
            "credential_url",
        ]


class HonorAwardReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertHonorAward
        fields = [
            "id",
            "title",
            "issuer",
            "issue_date",
            "description",
        ]


# ======================================================
# EXPERT PROFILE READ SERIALIZER
# (Public + expert self-view)
# ======================================================
class ExpertProfileReadSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)

    experiences = ExperienceReadSerializer(many=True, read_only=True)
    educations = EducationReadSerializer(many=True, read_only=True)
    certifications = CertificationReadSerializer(many=True, read_only=True)
    honors_awards = HonorAwardReadSerializer(many=True, read_only=True)

    class Meta:
        model = ExpertProfile
        fields = [
            "id",
            "uuid",
            "user",
            "first_name",
            "last_name",
            "headline",
            "profile_picture",
            "primary_expertise",
            "other_expertise",
            "hourly_rate",
            "is_available",
            "verified_by_admin",
            "application_status",
            "application_submitted_at",
            "admin_review_note",
            "experiences",
            "educations",
            "certifications",
            "honors_awards",
            "created_at",
            "updated_at",
        ]


# ======================================================
# EXPERT PROFILE WRITE SERIALIZER
# (For expert to create/update)
# ======================================================
class ExpertProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertProfile
        fields = [
            "first_name",
            "last_name",
            "headline",
            "profile_picture",
            "primary_expertise",
            "other_expertise",
            "hourly_rate",
            "is_available",
        ]


# ======================================================
# APPLICATION SUBMISSION SERIALIZER
# (Expert submits profile to admin)
# ======================================================
class ExpertApplicationSubmitSerializer(serializers.Serializer):
    """Expert submits profile → status changes to pending."""

    note = serializers.CharField(required=False)

    def save(self, expert_profile):
        expert_profile.application_status = "pending"
        expert_profile.application_submitted_at = timezone.now()
        expert_profile.admin_review_note = self.validated_data.get("note", "")
        expert_profile.save()
        return expert_profile


# ======================================================
# ADMIN VERIFICATION SERIALIZER
# ======================================================
class ExpertAdminVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    note = serializers.CharField(required=False)

    def save(self, expert_profile):
        action = self.validated_data["action"]

        if action == "approve":
            expert_profile.verified_by_admin = True
            expert_profile.application_status = "approved"
            expert_profile.user.user_type = "expert"
            expert_profile.user.save()

        else:
            expert_profile.verified_by_admin = False
            expert_profile.application_status = "rejected"

        expert_profile.admin_review_note = self.validated_data.get("note", "")
        expert_profile.save()
        return expert_profile


# ======================================================
# --- EXPERIENCE: CREATE / UPDATE SERIALIZER ---
# ======================================================
class ExperienceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertExperience
        fields = [
            "job_title",
            "company",
            "employment_type",
            "location",
            "start_date",
            "end_date",
            "description",
        ]


# ======================================================
# --- EDUCATION: CREATE / UPDATE SERIALIZER ---
# ======================================================
class EducationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertEducation
        fields = [
            "school",
            "degree",
            "field_of_study",
            "start_year",
            "end_year",
            "grade",
            "description",
        ]


# ======================================================
# --- CERTIFICATIONS: CREATE / UPDATE ---
# ======================================================
class CertificationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertCertification
        fields = [
            "name",
            "issuing_organization",
            "issue_date",
            "expiration_date",
            "credential_id",
            "credential_url",
        ]


# ======================================================
# --- HONORS / AWARDS: CREATE / UPDATE ---
# ======================================================
class HonorAwardWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertHonorAward
        fields = [
            "title",
            "issuer",
            "issue_date",
            "description",
        ]
