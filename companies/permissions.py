from rest_framework.permissions import BasePermission

from .models import CompanyMember


# =====================================================
# CHECK IF USER IS COMPANY OWNER
# =====================================================


class IsCompanyOwner(BasePermission):

    def has_object_permission(self, request, view, obj):

        return CompanyMember.objects.filter(
            company=obj, user=request.user, role="owner"
        ).exists()


# =====================================================
# CHECK IF USER IS COMPANY EDITOR OR OWNER
# =====================================================


class IsCompanyEditor(BasePermission):

    def has_permission(self, request, view):

        company_id = view.kwargs.get("company_id")

        if not company_id:
            return False

        return CompanyMember.objects.filter(
            company_id=company_id, user=request.user, role__in=["owner", "editor"]
        ).exists()


# =====================================================
# CHECK IF USER IS COMPANY MEMBER
# =====================================================


class IsCompanyMember(BasePermission):

    def has_permission(self, request, view):

        company_id = view.kwargs.get("company_id")

        if not company_id:
            return False

        return CompanyMember.objects.filter(
            company_id=company_id, user=request.user
        ).exists()
