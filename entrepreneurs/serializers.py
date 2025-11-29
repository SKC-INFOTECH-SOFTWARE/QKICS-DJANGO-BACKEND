from rest_framework import serializers
from django.utils import timezone
from .models import EntrepreneurProfile
from django.contrib.auth import get_user_model

User = get_user_model()


class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "user_type", ]


# READ – Public List & Detail + Self Dashboard
class EntrepreneurProfileReadSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = EntrepreneurProfile
        fields = [
            "id", "user", "is_owner",
            "startup_name", "one_liner", "description",
            "website", "logo", "industry", "location",
            "funding_stage", "verified_by_admin",
            "application_status", "created_at", "updated_at",
        ]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return request and request.user.is_authenticated and obj.user_id == request.user.id


# WRITE – Create & Update Own Profile
class EntrepreneurProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntrepreneurProfile
        fields = [
            "startup_name", "one_liner", "description",
            "website", "logo", "industry", "location", "funding_stage"
        ]


# Submit Application → pending
class EntrepreneurApplicationSubmitSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def save(self, profile):
        profile.application_status = "pending"
        profile.save(update_fields=["application_status", "updated_at"])
        return profile


# Admin Approval/Rejection
class EntrepreneurAdminVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    note = serializers.CharField(required=False, allow_blank=True)

    def save(self, profile):
        action = self.validated_data["action"]

        if action == "approve":
            profile.verified_by_admin = True
            profile.application_status = "approved"
            profile.user.user_type = "entrepreneur"
            profile.user.save()
        else:
            profile.verified_by_admin = False
            profile.application_status = "rejected"

        profile.save()
        return profile