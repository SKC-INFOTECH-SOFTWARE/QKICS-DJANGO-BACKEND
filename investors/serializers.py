from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Investor, Industry, StartupStage

User = get_user_model()


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ["id", "name"]


class StartupStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = StartupStage
        fields = ["id", "name"]


class InvestorReadSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    focus_industries = IndustrySerializer(many=True)
    preferred_stages = StartupStageSerializer(many=True)
    investor_type_display = serializers.CharField(source="get_investor_type_display", read_only=True)

    class Meta:
        model = Investor
        fields = [
            "id", "user", "profile_picture", "display_name", "one_liner", "investment_thesis",
            "focus_industries", "preferred_stages", "check_size_min", "check_size_max",
            "location", "website_url", "linkedin_url", "twitter_url",
            "investor_type", "investor_type_display", "verified_by_admin", "is_active",
            "created_at", "updated_at"
        ]
    
    def get_user(self, obj):
        return {"id": obj.user.id,"uuid":obj.user.uuid,  "username": obj.user.username,"first_name": obj.user.first_name, "last_name": obj.user.last_name, "user_type": obj.user.user_type, "profile_picture": obj.user.profile_picture.url if obj.user.profile_picture else None}

    def get_profile_picture(self, obj):
        if not obj.user.profile_picture:
            return None

        request = self.context.get("request")
        url = obj.user.profile_picture.url

        return request.build_absolute_uri(url) if request else url



class InvestorWriteSerializer(serializers.ModelSerializer):
    focus_industries = serializers.PrimaryKeyRelatedField(queryset=Industry.objects.all(), many=True, required=False)
    preferred_stages = serializers.PrimaryKeyRelatedField(queryset=StartupStage.objects.all(), many=True, required=False)

    class Meta:
        model = Investor
        fields = [
            "display_name", "one_liner", "investment_thesis",
            "focus_industries", "preferred_stages",
            "check_size_min", "check_size_max", "location",
            "website_url", "linkedin_url", "twitter_url", "investor_type"
        ]


class InvestorAdminVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    note = serializers.CharField(required=False, allow_blank=True)

    def save(self, investor):
        action = self.validated_data["action"]
        if action == "approve":
            investor.verified_by_admin = True
            investor.application_status = "approved"
            investor.user.user_type = "investor"
            investor.user.save()
        else:
            investor.verified_by_admin = False
            investor.application_status = "rejected"
        investor.save()
        return investor