from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from users.permissions import IsAdmin
from adminpanel.pagination import AdminPagination
from adminpanel.serializers import AdminAdvertisementSerializer
from ads.models import Advertisement


class AdminAdvertisementListView(ListAPIView):
    """
    Admin: List all advertisements
    """

    queryset = Advertisement.objects.select_related("created_by").all()
    serializer_class = AdminAdvertisementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]

    filterset_fields = [
        "placement",
        "media_type",
        "is_active",
    ]

    search_fields = [
        "title",
        "description",
        "created_by__username",
    ]

    ordering_fields = [
        "created_at",
        "start_datetime",
        "end_datetime",
        "is_active",
    ]

    ordering = ["-created_at"]