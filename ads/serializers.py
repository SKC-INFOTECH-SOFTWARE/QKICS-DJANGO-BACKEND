from rest_framework import serializers
from ads.models import Advertisement


class PublicAdvertisementSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Advertisement
        fields = [
            "id",
            "uuid",
            "title",
            "description",
            "media_type",
            "file_url",
            "redirect_url",
            "button_text",
            "placement",
        ]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None
