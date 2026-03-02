from rest_framework.generics import (
    ListAPIView,
    CreateAPIView,
    UpdateAPIView,
    DestroyAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from users.permissions import IsAdmin
from adminpanel.pagination import AdminPagination
from adminpanel.serializers import (
    AdminAdvertisementSerializer,
    AdminAdvertisementCreateSerializer,
    AdminAdvertisementUpdateSerializer,
)
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


class AdminAdvertisementCreateView(CreateAPIView):
    """
    Admin: Create new advertisement
    """

    queryset = Advertisement.objects.all()
    serializer_class = AdminAdvertisementCreateSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


class AdminAdvertisementUpdateView(UpdateAPIView):
    """
    Admin: Update advertisement
    """

    queryset = Advertisement.objects.all()
    serializer_class = AdminAdvertisementUpdateSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_field = "id"


class AdminAdvertisementDeleteView(DestroyAPIView):
    """
    Admin: Delete advertisement
    """

    queryset = Advertisement.objects.all()
    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_field = "id"
