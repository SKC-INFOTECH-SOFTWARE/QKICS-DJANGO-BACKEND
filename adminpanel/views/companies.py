from rest_framework import generics
from rest_framework.permissions import IsAdminUser
from django.shortcuts import get_object_or_404

from companies.models import Company, CompanyMember, CompanyPost

from adminpanel.serializers import (
    AdminCompanySerializer,
    AdminCompanyMemberSerializer,
    AdminCompanyPostSerializer,
)

from adminpanel.pagination import AdminCursorPagination, AdminMemberCursorPagination
from notifications.services.events import (
    notify_company_approved,
    notify_company_rejected,
)

# =====================================================
# LIST ALL COMPANIES
# =====================================================


class AdminCompanyListView(generics.ListAPIView):
    queryset = Company.objects.select_related("owner").all().order_by("-created_at")
    serializer_class = AdminCompanySerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminCursorPagination


# =====================================================
# VIEW SINGLE COMPANY
# =====================================================


class AdminCompanyDetailView(generics.RetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = AdminCompanySerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"


# =====================================================
# UPDATE COMPANY
# =====================================================


class AdminCompanyUpdateView(generics.UpdateAPIView):
    queryset = Company.objects.all()
    serializer_class = AdminCompanySerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"

    def perform_update(self, serializer):
        old_status = self.get_object().status
        company = serializer.save()
        new_status = company.status

        # Fire notification only when status actually changes
        if old_status != new_status:
            if new_status == "approved":
                notify_company_approved(company)
            elif new_status == "rejected":
                notify_company_rejected(company)


# =====================================================
# DELETE COMPANY
# =====================================================


class AdminCompanyDeleteView(generics.DestroyAPIView):
    queryset = Company.objects.all()
    serializer_class = AdminCompanySerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"


# =====================================================
# LIST COMPANY MEMBERS
# =====================================================


class AdminCompanyMembersView(generics.ListAPIView):
    serializer_class = AdminCompanyMemberSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminMemberCursorPagination

    def get_queryset(self):
        company_id = self.kwargs["company_uuid"]

        company = get_object_or_404(Company, id=company_id)

        return CompanyMember.objects.filter(company=company).select_related("user")


# =====================================================
# REMOVE MEMBER
# =====================================================


class AdminCompanyMemberRemoveView(generics.DestroyAPIView):
    queryset = CompanyMember.objects.all()
    serializer_class = AdminCompanyMemberSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"


# =====================================================
# LIST COMPANY POSTS
# =====================================================


class AdminCompanyPostsView(generics.ListAPIView):
    serializer_class = AdminCompanyPostSerializer
    permission_classes = [IsAdminUser]
    pagination_class = AdminCursorPagination

    def get_queryset(self):
        company_id = self.kwargs["company_uuid"]

        company = get_object_or_404(Company, id=company_id)

        return (
            CompanyPost.objects.filter(company=company)
            .select_related("author")
            .order_by("-created_at")
        )


# =====================================================
# DELETE COMPANY POST
# =====================================================


class AdminCompanyPostDeleteView(generics.DestroyAPIView):
    queryset = CompanyPost.objects.all()
    serializer_class = AdminCompanyPostSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"
