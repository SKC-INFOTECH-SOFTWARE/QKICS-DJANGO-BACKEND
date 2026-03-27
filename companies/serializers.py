from rest_framework import serializers
from django.contrib.auth import get_user_model

from users.serializers import CompanyUser

from .models import (
    Company,
    CompanyMember,
    CompanyPost,
    CompanyPostMedia,
)

User = get_user_model()


# =====================================================
# COMPANY MEMBER SERIALIZER
# =====================================================


class CompanyMemberSerializer(serializers.ModelSerializer):
    user = CompanyUser(read_only=True)

    class Meta:
        model = CompanyMember
        fields = [
            "id",
            "user",
            "role",
            "joined_at",
        ]
        read_only_fields = ["id", "joined_at"]


# =====================================================
# COMPANY SERIALIZER
# =====================================================


class CompanySerializer(serializers.ModelSerializer):

    owner = serializers.StringRelatedField(read_only=True)
    members = CompanyMemberSerializer(many=True, read_only=True)

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "cover_image",
            "description",
            "industry",
            "website",
            "location",
            "owner",
            "status",
            "members",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "slug",
            "owner",
            "status",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):

        request = self.context["request"]

        company = Company.objects.create(owner=request.user, **validated_data)

        # Create owner membership
        CompanyMember.objects.create(company=company, user=request.user, role="owner")

        return company


# =====================================================
# COMPANY POST MEDIA SERIALIZER
# =====================================================


class CompanyPostMediaSerializer(serializers.ModelSerializer):

    class Meta:
        model = CompanyPostMedia
        fields = [
            "id",
            "file",
            "media_type",
            "uploaded_at",
        ]

        read_only_fields = [
            "id",
            "media_type",
            "uploaded_at",
        ]


# =====================================================
# COMPANY POST SERIALIZER
# =====================================================


class CompanyPostCompanySerializer(serializers.ModelSerializer):

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "slug",
            "logo",
        ]


class CompanyPostSerializer(serializers.ModelSerializer):

    author = serializers.StringRelatedField(read_only=True)
    company = CompanyPostCompanySerializer(read_only=True)
    media = CompanyPostMediaSerializer(many=True, read_only=True)

    class Meta:
        model = CompanyPost
        fields = [
            "id",
            "company",
            "author",
            "title",
            "content",
            "media",
            "created_at",
            "updated_at",
            "is_active",
        ]

        read_only_fields = [
            "id",
            "company",
            "author",
            "created_at",
            "updated_at",
            "is_active",
        ]

    def create(self, validated_data):
        request = self.context.get("request")

        post = CompanyPost.objects.create(**validated_data)
        if request and request.FILES:
            files = request.FILES.getlist("uploaded_files")

            for file in files:
                CompanyPostMedia.objects.create(post=post, file=file)

        return post
