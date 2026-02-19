from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Prefetch

from entrepreneurs.models import EntrepreneurProfile
from entrepreneurs.serializers import EntrepreneurProfileReadSerializer
from users.permissions import IsAdmin
from adminpanel.pagination import AdminPagination


class AdminEntrepreneurApplicationListView(ListAPIView):
    """
    Admin: List all entrepreneur applications.
    """
    queryset = EntrepreneurProfile.objects.select_related("user").all()
    serializer_class = EntrepreneurProfileReadSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [SearchFilter, OrderingFilter]

    search_fields = [
        "user__username",
        "user__email",
        "startup_name",
        "industry",
        "location",
    ]

    ordering_fields = [
        "application_status",
        "created_at",
        "funding_stage",
    ]
