# users/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "superadmin"
        )


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type in ["superadmin", "admin"]
        )


class IsExpert(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "expert"
            and request.user.is_verified
        )


class IsInvestor(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "investor"
            and request.user.is_verified
        )


class IsEntrepreneur(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "entrepreneur"
            and request.user.is_verified
        )


class IsNormalUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == "normal"


class IsOwnerOrAdmin(BasePermission):
    """Allow owner of object or admin/superadmin"""
    def has_object_permission(self, request, view, obj):
        return (
            obj == request.user or
            request.user.user_type in ["admin", "superadmin"]
        )