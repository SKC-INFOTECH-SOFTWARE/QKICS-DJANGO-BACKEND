from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status as http_status
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from adminpanel.pagination import AdminPagination
from adminpanel.serializers import (
    AdminFullUserSerializer,
    AdminUserStatusSerializer,
)
from users.permissions import IsAdmin

User = get_user_model()


class AdminUserListView(ListAPIView):
    """
    Admin: List all users with search and ordering support.
    """

    queryset = User.objects.all().order_by("-created_at")
    serializer_class = AdminFullUserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = AdminPagination

    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filterset_fields = ["user_type", "status", "is_active"]

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
        "status",
    ]


def _revoke_refresh_tokens(user):
    """Blacklist every outstanding refresh token for `user`.

    Access tokens are stateless and are stopped by the `is_active` sync below
    (SimpleJWT's CHECK_USER_IS_ACTIVE); this stops a blocked user from minting
    a fresh access token with a refresh token they already hold.
    Returns the number of tokens blacklisted (0 if the blacklist app is absent).
    """
    try:
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken,
            OutstandingToken,
        )
    except ImportError:  # blacklist app not installed
        return 0

    count = 0
    for token in OutstandingToken.objects.filter(user=user):
        _, created = BlacklistedToken.objects.get_or_create(token=token)
        if created:
            count += 1
    return count


class AdminUserStatusUpdateView(APIView):
    """
    Admin: block / unblock / deactivate a user account.

    PATCH /api/v1/admin/users/<id>/status/   {"status": "banned", "reason": "spam"}

    Sets the business `status` AND Django's `is_active` together so the change
    takes effect immediately — an already-issued access token is rejected on the
    next request instead of staying valid until it expires.
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, id):
        try:
            target = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response(
                {"detail": "User not found."},
                status=http_status.HTTP_404_NOT_FOUND,
            )

        actor = request.user

        # An admin may not lock themselves out.
        if target.id == actor.id:
            return Response(
                {"detail": "You cannot change your own account status."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        # Only a superadmin may act on admins and superadmins.
        if target.user_type in ("admin", "superadmin") and actor.user_type != "superadmin":
            return Response(
                {"detail": "Only a superadmin can change an admin account's status."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        serializer = AdminUserStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        reason = serializer.validated_data.get("reason", "")

        with transaction.atomic():
            target.status = new_status
            target.is_active = new_status == "active"
            target.status_reason = reason
            target.status_changed_at = timezone.now()
            target.status_changed_by = actor
            target.save(
                update_fields=[
                    "status",
                    "is_active",
                    "status_reason",
                    "status_changed_at",
                    "status_changed_by",
                    "updated_at",
                ]
            )

            revoked = 0
            if new_status != "active":
                revoked = _revoke_refresh_tokens(target)

        return Response(
            {
                "id": target.id,
                "username": target.username,
                "status": target.status,
                "is_active": target.is_active,
                "status_reason": target.status_reason,
                "status_changed_at": target.status_changed_at,
                "sessions_revoked": revoked,
            },
            status=http_status.HTTP_200_OK,
        )
