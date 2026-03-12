from rest_framework import serializers
from django.contrib.auth import get_user_model
from ads.models import Advertisement
from companies.models import Company, CompanyMember, CompanyPost

User = get_user_model()


class AdminFullUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ["password"]


class AdminAdvertisementSerializer(serializers.ModelSerializer):
    created_by = serializers.StringRelatedField()

    class Meta:
        model = Advertisement
        fields = "__all__"


class AdminAdvertisementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        exclude = [
            "uuid",
            "media_type",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["created_by"] = request.user
        return super().create(validated_data)


class AdminAdvertisementUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Advertisement
        exclude = [
            "uuid",
            "media_type",
            "created_by",
            "created_at",
            "updated_at",
        ]


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class AdminCompanySerializer(serializers.ModelSerializer):

    owner = AdminUserSerializer(read_only=True)

    class Meta:
        model = Company
        fields = [
            "uuid",
            "name",
            "description",
            "owner",
            "created_at",
            "updated_at",
            "is_active",
        ]
        read_only_fields = [
            "uuid",
            "owner",
            "created_at",
            "updated_at",
        ]


class AdminCompanyMemberSerializer(serializers.ModelSerializer):

    user = AdminUserSerializer(read_only=True)

    class Meta:
        model = CompanyMember
        fields = ["uuid", "user", "role", "joined_at"]


class AdminCompanyPostSerializer(serializers.ModelSerializer):

    author = AdminUserSerializer(read_only=True)

    class Meta:
        model = CompanyPost
        fields = ["uuid", "author", "content", "created_at", "updated_at"]
