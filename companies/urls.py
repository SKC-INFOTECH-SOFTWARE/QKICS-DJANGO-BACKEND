from django.urls import path
from .views import (
    CompanyCreateView,
    CompanyListView,
    CompanyDetailView,
    CompanyUpdateView,
)

urlpatterns = [
    path("", CompanyCreateView.as_view(), name="company-create"),
    path("list/", CompanyListView.as_view(), name="company-list"),
    path("<slug:slug>/", CompanyDetailView.as_view(), name="company-detail"),
    path("<uuid:pk>/update/", CompanyUpdateView.as_view(), name="company-update"),
]
