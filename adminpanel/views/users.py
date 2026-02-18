from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from users.permissions import IsAdmin as IsAdminUserType
from adminpanel.serializers import AdminFullUserSerializer
from adminpanel.pagination import AdminPagination

User = get_user_model()


class AdminUserListView(ListAPIView):
    """
    Admin: List ALL users with full model details (except password).
    """
    queryset = User.objects.all().order_by("-created_at")
    serializer_class = AdminFullUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserType]
    pagination_class = AdminPagination
