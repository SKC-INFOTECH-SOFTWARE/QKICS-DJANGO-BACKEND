from rest_framework import serializers
from django.contrib.auth import get_user_model
from ads.models import Advertisement

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
