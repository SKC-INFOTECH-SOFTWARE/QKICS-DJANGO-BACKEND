from django.urls import path
from .views import (
    CompanyCreateView,
    CompanyListView,
    CompanyDetailView,
    CompanyUpdateView,
    CompanyMemberListView,
    CompanyAddEditorView,
    CompanyRemoveEditorView,
    CompanyPostCreateView,
    CompanyPostListView,
    CompanyPostFeedView,
    CompanyPostUpdateView,
    CompanyPostDeleteView,
    MyCompaniesView,
)

urlpatterns = [
    path("my/", MyCompaniesView.as_view(), name="my-companies"),
    path("", CompanyCreateView.as_view(), name="company-create"),
    path("list/", CompanyListView.as_view(), name="company-list"),

    # Global posts feed
    path("posts/", CompanyPostFeedView.as_view(), name="company-post-feed"),
    path("posts/<uuid:pk>/update/", CompanyPostUpdateView.as_view(), name="company-post-update"),
    path("posts/<uuid:pk>/delete/", CompanyPostDeleteView.as_view(), name="company-post-delete"),

    # Company post routes
    path("<uuid:company_id>/posts/", CompanyPostListView.as_view(), name="company-posts"),
    path("<uuid:company_id>/posts/create/", CompanyPostCreateView.as_view(), name="company-post-create"),

    # Company members
    path("<uuid:company_id>/members/", CompanyMemberListView.as_view(), name="company-members"),
    path("<uuid:company_id>/members/add/", CompanyAddEditorView.as_view(), name="company-add-editor"),
    path("<uuid:company_id>/members/<uuid:user_id>/remove/", CompanyRemoveEditorView.as_view(), name="company-remove-editor"),

    # Company update
    path("<uuid:pk>/update/", CompanyUpdateView.as_view(), name="company-update"),

    # Company detail (MUST BE LAST)
    path("<slug:slug>/", CompanyDetailView.as_view(), name="company-detail"),
]
