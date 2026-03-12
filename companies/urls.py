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
from .views import (
    CompanyPostCreateView,
    CompanyPostListView,
    CompanyPostFeedView,
    CompanyPostUpdateView,
    CompanyPostDeleteView,
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
    # Company posts
    path(
        "<uuid:company_id>/posts/", CompanyPostListView.as_view(), name="company-posts"
    ),
    path(
        "<uuid:company_id>/posts/create/",
        CompanyPostCreateView.as_view(),
        name="company-post-create",
    ),
    # Global feed
    path("posts/", CompanyPostFeedView.as_view(), name="company-post-feed"),
    # Update post
    path(
        "posts/<uuid:pk>/update/",
        CompanyPostUpdateView.as_view(),
        name="company-post-update",
    ),
    # Delete post
    path(
        "posts/<uuid:pk>/delete/",
        CompanyPostDeleteView.as_view(),
        name="company-post-delete",
    ),
]
