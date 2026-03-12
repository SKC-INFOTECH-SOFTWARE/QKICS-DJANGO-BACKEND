from rest_framework import generics, permissions
from django.shortcuts import get_object_or_404

from .models import Company
from .serializers import CompanySerializer
from .permissions import IsCompanyOwner


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