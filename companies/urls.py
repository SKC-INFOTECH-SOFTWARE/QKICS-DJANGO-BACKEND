from django.urls import path
from .views import (
    CompanyCreateView,
    CompanyListView,
    CompanyDetailView,
    CompanyUpdateView,
)
from .views import (
    CompanyMemberListView,
    CompanyAddEditorView,
    CompanyRemoveEditorView,
)

urlpatterns = [
    path("", CompanyCreateView.as_view(), name="company-create"),
    path("list/", CompanyListView.as_view(), name="company-list"),
    path("<slug:slug>/", CompanyDetailView.as_view(), name="company-detail"),
    path("<uuid:pk>/update/", CompanyUpdateView.as_view(), name="company-update"),
    path(
        "<uuid:company_id>/members/",
        CompanyMemberListView.as_view(),
        name="company-members",
    ),
    path(
        "<uuid:company_id>/members/add/",
        CompanyAddEditorView.as_view(),
        name="company-add-editor",
    ),
    path(
        "<uuid:company_id>/members/<uuid:user_id>/remove/",
        CompanyRemoveEditorView.as_view(),
        name="company-remove-editor",
    ),
]
