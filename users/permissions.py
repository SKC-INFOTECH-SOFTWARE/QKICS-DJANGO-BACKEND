from rest_framework.permissions import BasePermission


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
    """
    Expert must:
    - be authenticated
    - be user_type == 'expert'
    - have a verified ExpertProfile
    """
    def has_permission(self, request, view):
        user = request.user

        if not (user.is_authenticated and user.user_type == "expert"):
            return False

        # ExpertProfile verification
        if hasattr(user, "expert_profile"):
            return user.expert_profile.verified_by_admin

        return False


class IsInvestor(BasePermission):
    """
    Keep user_type check only for now,
    because investor_profile is not yet implemented.
    Add verified check later.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "investor"
        )


class IsEntrepreneur(BasePermission):
    """
    Keep user_type check only for now,
    until EntrepreneurProfile is implemented.
    """
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "entrepreneur"
        )


class IsNormalUser(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.user_type == "normal"
        )


class IsOwnerOrAdmin(BasePermission):
    """Allow owner of object OR admin/superadmin."""
    def has_object_permission(self, request, view, obj):
        return (
            obj == request.user
            or request.user.user_type in ["admin", "superadmin"]
        )
