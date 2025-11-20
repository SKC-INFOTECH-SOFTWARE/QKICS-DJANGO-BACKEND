from rest_framework import serializers
from .models import EntrepreneurProfile, ExpertProfile


class EntrepreneurProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)

    class Meta:
        model = EntrepreneurProfile
        fields = [
            "id",
            "username",
            "email",
            "is_verified",
            "company_name",
            "tagline",
            "website",
            "pitch_deck",
            "problem_statement",
            "solution",
            "market_size",
            "traction",
            "funding_ask",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ExpertProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.get_full_name", read_only=True)
    is_verified = serializers.BooleanField(source="user.is_verified", read_only=True)

    class Meta:
        model = ExpertProfile
        fields = [
            "id",
            "username",
            "full_name",
            "is_verified",
            "bio",
            "expertise",
            "hourly_rate",
            "linkedin",
            "resume",
            "is_available",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
