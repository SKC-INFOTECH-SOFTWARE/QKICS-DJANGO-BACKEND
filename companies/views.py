from rest_framework import generics
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination
from rest_framework.exceptions import PermissionDenied

from .models import Company, CompanyMember, CompanyPost
from .serializers import (
    CompanySerializer,
    CompanyPostSerializer,
    CompanyMemberSerializer,
)
from .permissions import IsCompanyOwner, IsCompanyEditor


# =====================================================
# PAGINATION
# =====================================================


class CompanyCursorPagination(CursorPagination):
    page_size = 10
    ordering = "-created_at"


# =====================================================
# CREATE COMPANY
# =====================================================


class CompanyCreateView(generics.CreateAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]


# =====================================================
# LIST COMPANIES
# =====================================================


class CompanyListView(generics.ListAPIView):
    serializer_class = CompanySerializer
    permission_classes = [AllowAny]
    pagination_class = CompanyCursorPagination

    def get_queryset(self):
        return Company.objects.filter(status="approved").select_related("owner")


# =====================================================
# COMPANY DETAIL
# =====================================================


class CompanyDetailView(generics.RetrieveAPIView):
    serializer_class = CompanySerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    queryset = Company.objects.filter(status="approved").select_related("owner")


# =====================================================
# UPDATE COMPANY
# =====================================================


class CompanyUpdateView(generics.UpdateAPIView):
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, IsCompanyOwner]

    def get_queryset(self):
        return Company.objects.filter(owner=self.request.user)


# =====================================================
# MY LIST COMPANY
# =====================================================
class MyCompaniesView(generics.ListAPIView):

    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CompanyCursorPagination

    def get_queryset(self):
        return (
            Company.objects.filter(members__user=self.request.user)
            .select_related("owner")
            .prefetch_related("members__user")
            .distinct()
        )


# =====================================================
# LIST COMPANY MEMBERS
# =====================================================


class CompanyMemberListView(generics.ListAPIView):
    serializer_class = CompanyMemberSerializer
    permission_classes = [IsAuthenticated, IsCompanyOwner]

    def get_queryset(self):
        company_id = self.kwargs["company_id"]

        return CompanyMember.objects.filter(company_id=company_id).select_related(
            "user"
        )


# =====================================================
# ADD EDITOR
# =====================================================


class CompanyAddEditorView(generics.CreateAPIView):
    serializer_class = CompanyMemberSerializer
    permission_classes = [IsAuthenticated, IsCompanyOwner]

    def create(self, request, *args, **kwargs):

        company_id = self.kwargs["company_id"]
        company = get_object_or_404(Company, id=company_id)

        user_id = request.data.get("user_id")

        member, created = CompanyMember.objects.get_or_create(
            company=company,
            user_id=user_id,
            defaults={"role": "editor"},
        )

        if not created:
            return Response(
                {"detail": "User is already a member of this company"},
                status=400,
            )

        serializer = self.get_serializer(member)

        return Response(serializer.data)


# =====================================================
# REMOVE EDITOR
# =====================================================


class CompanyRemoveEditorView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsCompanyOwner]

    def delete(self, request, *args, **kwargs):

        company_id = self.kwargs["company_id"]
        user_id = self.kwargs["user_id"]

        member = get_object_or_404(
            CompanyMember,
            company_id=company_id,
            user_id=user_id,
            role="editor",
        )

        member.delete()

        return Response({"detail": "Editor removed successfully"})


# =====================================================
# CREATE COMPANY POST
# =====================================================


class CompanyPostCreateView(generics.CreateAPIView):
    serializer_class = CompanyPostSerializer
    permission_classes = [IsAuthenticated, IsCompanyEditor]

    def perform_create(self, serializer):

        company_id = self.kwargs["company_id"]
        company = get_object_or_404(Company, id=company_id)

        if company.status != "approved":
            raise PermissionDenied("Company is not allowed to create posts.")

        serializer.save(company=company, author=self.request.user)


# =====================================================
# LIST COMPANY POSTS
# =====================================================


class CompanyPostListView(generics.ListAPIView):
    serializer_class = CompanyPostSerializer
    permission_classes = [AllowAny]
    pagination_class = CompanyCursorPagination

    def get_queryset(self):

        company_id = self.kwargs["company_id"]

        return (
            CompanyPost.objects.filter(
                company_id=company_id,
                is_active=True,
            )
            .select_related(
                "author",
                "company",
            )
            .prefetch_related("media")
        )


# =====================================================
# GLOBAL COMPANY POSTS FEED
# =====================================================


class CompanyPostFeedView(generics.ListAPIView):
    serializer_class = CompanyPostSerializer
    permission_classes = [AllowAny]
    pagination_class = CompanyCursorPagination

    queryset = (
        CompanyPost.objects.filter(
            is_active=True,
            company__status="approved",
        )
        .select_related(
            "author",
            "company",
        )
        .prefetch_related("media")
    )


# =====================================================
# UPDATE COMPANY POST
# =====================================================


class CompanyPostUpdateView(generics.UpdateAPIView):
    serializer_class = CompanyPostSerializer
    permission_classes = [IsAuthenticated, IsCompanyEditor]

    def get_queryset(self):
        return CompanyPost.objects.filter(author=self.request.user)


# =====================================================
# DELETE COMPANY POST
# =====================================================


class CompanyPostDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsCompanyEditor]

    def get_queryset(self):
        return CompanyPost.objects.filter(author=self.request.user)
