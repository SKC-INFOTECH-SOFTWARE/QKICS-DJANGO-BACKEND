from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from rest_framework.filters import SearchFilter, OrderingFilter

from users.permissions import IsAdmin
from adminpanel.serializers import AdminFullUserSerializer
from adminpanel.pagination import AdminPagination

User = get_user_model()


class AdminUserListView(ListAPIView):
    """
    Admin: List all users with search and ordering support.
    """
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = AdminFullUserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [SearchFilter, OrderingFilter]

    search_fields = [
        "username",
        "email",
        "phone",
        "first_name",
        "last_name",
    ]

    ordering_fields = [
        "created_at",
        "username",
        "date_joined",
        "user_type",
    ]
