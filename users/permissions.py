# users/permissions.py

from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "superadmin"


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in [
            "superadmin",
            "admin",
        ]


class IsExpert(BasePermission):
    """Verified expert with approved ExpertProfile"""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "expert"
            and hasattr(request.user, "expert_profile")
            and request.user.expert_profile.verified_by_admin
            and request.user.expert_profile.application_status == "approved"
        )


class IsEntrepreneur(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "entrepreneur"
            and hasattr(request.user, "entrepreneur_profile")
            and request.user.entrepreneur_profile.verified_by_admin
            and request.user.entrepreneur_profile.application_status == "approved"
        )


class IsInvestor(BasePermission):
    """Verified investor — will be created & verified by admin"""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "investor"
            and hasattr(request.user, "investor_profile")
            and request.user.investor_profile.verified_by_admin
            and request.user.investor_profile.application_status == "approved"
        )


class IsNormalUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "normal"


class IsPremiumUser(BasePermission):
    """User has active premium subscription"""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and hasattr(request.user, "subscription")
            and request.user.subscription.is_active
        )


class IsOwnerOrAdmin(BasePermission):
    """Allow owner of object OR admin/superadmin"""

    def has_object_permission(self, request, view, obj):
        # Works for objects that have .user field (e.g. Profile, Post, etc.)
        if hasattr(obj, "user"):
            return obj.user == request.user or request.user.user_type in [
                "admin",
                "superadmin",
            ]
        return request.user.user_type in ["admin", "superadmin"]
