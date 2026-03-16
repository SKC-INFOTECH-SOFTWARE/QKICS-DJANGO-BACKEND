from rest_framework.permissions import BasePermission

from .models import CompanyMember, CompanyPost


# =====================================================
# CHECK IF USER IS COMPANY OWNER
# =====================================================

class IsCompanyOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        return CompanyMember.objects.filter(
            company=obj,
            user=request.user,
            role="owner"
        ).exists()


# =====================================================
# CHECK IF USER IS COMPANY EDITOR OR OWNER
# =====================================================

class IsCompanyEditor(BasePermission):

    def has_permission(self, request, view):

        # Case 1: endpoints with company_id in URL
        company_id = view.kwargs.get("company_id")

        if company_id:
            return CompanyMember.objects.filter(
                company_id=company_id,
                user=request.user,
                role__in=["owner", "editor"]
            ).exists()

        # Case 2: endpoints with post_id in URL
        post_id = view.kwargs.get("pk")

        if post_id:
            try:
                post = CompanyPost.objects.select_related("company").get(pk=post_id)
            except CompanyPost.DoesNotExist:
                return False

            return CompanyMember.objects.filter(
                company=post.company,
                user=request.user,
                role__in=["owner", "editor"]
            ).exists()

        return False


# =====================================================
# CHECK IF USER IS COMPANY MEMBER
# =====================================================

class IsCompanyMember(BasePermission):

    def has_permission(self, request, view):

        company_id = view.kwargs.get("company_id")

        if not company_id:
            return False

        return CompanyMember.objects.filter(
            company_id=company_id,
            user=request.user
        ).exists()