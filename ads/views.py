from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from django.utils import timezone

from ads.models import Advertisement
from ads.serializers import PublicAdvertisementSerializer


class PublicActiveAdvertisementView(ListAPIView):
    """
    Public: Fetch active and currently running ads by placement
    """

    serializer_class = PublicAdvertisementSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        placement = self.request.query_params.get("placement")
        now = timezone.now()

        queryset = Advertisement.objects.filter(
            is_active=True,
            start_datetime__lte=now,
            end_datetime__gte=now,
        )

        if placement:
            queryset = queryset.filter(placement=placement)

        return queryset.select_related("created_by").order_by("-created_at")
