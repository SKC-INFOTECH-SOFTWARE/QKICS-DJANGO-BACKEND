from rest_framework import generics, permissions
from django.shortcuts import get_object_or_404
from .serializers import CompanySerializer, CompanyPostSerializer
from .permissions import IsCompanyOwner, IsCompanyEditor
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Company, CompanyMember, CompanyPost
from .serializers import CompanyMemberSerializer
from rest_framework.response import Response
from rest_framework.pagination import CursorPagination


# Pagination Class
class CompanyPostCursorPagination(CursorPagination):

    page_size = 10
    ordering = "-created_at"


# =====================================================
# CREATE COMPANY
# =====================================================


class CompanyCreateView(generics.CreateAPIView):

    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]


# =====================================================
# LIST COMPANIES
# =====================================================


class CompanyListView(generics.ListAPIView):

    serializer_class = CompanySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):

        return Company.objects.filter(status="approved")


# =====================================================
# COMPANY DETAIL
# =====================================================


class CompanyDetailView(generics.RetrieveAPIView):

    serializer_class = CompanySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    queryset = Company.objects.filter(status="approved")


# =====================================================
# UPDATE COMPANY
# =====================================================


class CompanyUpdateView(generics.UpdateAPIView):

    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated, IsCompanyOwner]
    queryset = Company.objects.all()


# =====================================================
# LIST COMPANY MEMBERS
# =====================================================


class CompanyMemberListView(generics.ListAPIView):

    serializer_class = CompanyMemberSerializer
    permission_classes = [IsAuthenticated, IsCompanyOwner]

    def get_queryset(self):

        company_id = self.kwargs["company_id"]

        return CompanyMember.objects.filter(company_id=company_id)


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

        member = CompanyMember.objects.create(
            company=company, user_id=user_id, role="editor"
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
            CompanyMember, company_id=company_id, user_id=user_id, role="editor"
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

        serializer.save(company=company, author=self.request.user)


# =====================================================
# LIST COMPANY POSTS
# =====================================================


class CompanyPostListView(generics.ListAPIView):

    serializer_class = CompanyPostSerializer
    permission_classes = [AllowAny]
    pagination_class = CompanyPostCursorPagination

    def get_queryset(self):

        company_id = self.kwargs["company_id"]

        return CompanyPost.objects.filter(company_id=company_id, is_active=True)


# =====================================================
# GLOBAL COMPANY POSTS FEED
# =====================================================


class CompanyPostFeedView(generics.ListAPIView):

    serializer_class = CompanyPostSerializer
    permission_classes = [AllowAny]
    pagination_class = CompanyPostCursorPagination

    queryset = CompanyPost.objects.filter(is_active=True, company__status="approved")


# =====================================================
# UPDATE COMPANY POST
# =====================================================


class CompanyPostUpdateView(generics.UpdateAPIView):

    serializer_class = CompanyPostSerializer
    permission_classes = [IsAuthenticated, IsCompanyEditor]

    queryset = CompanyPost.objects.all()


# =====================================================
# DELETE COMPANY POST
# =====================================================


class CompanyPostDeleteView(generics.DestroyAPIView):

    permission_classes = [IsAuthenticated, IsCompanyEditor]

    queryset = CompanyPost.objects.all()
