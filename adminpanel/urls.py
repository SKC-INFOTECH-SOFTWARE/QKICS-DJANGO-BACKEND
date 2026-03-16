from django.urls import path
from .views.users import AdminUserListView
from .views.experts import (
    AdminExpertApplicationListView,
    AdminExpertApplicationUpdateView,
)
from .views.entrepreneurs import (
    AdminEntrepreneurApplicationListView,
    AdminEntrepreneurApplicationUpdateView,
)
from .views.ads import (
    AdminAdvertisementListView,
    AdminAdvertisementCreateView,
    AdminAdvertisementUpdateView,
    AdminAdvertisementDeleteView,
)
from .views.companies import (
    AdminCompanyListView,
    AdminCompanyDetailView,
    AdminCompanyUpdateView,
    AdminCompanyDeleteView,
    AdminCompanyMembersView,
    AdminCompanyMemberRemoveView,
    AdminCompanyPostsView,
    AdminCompanyPostDeleteView,
)
from .views.company_settings import CompanyPostSettingsView

urlpatterns = [
    # Admin user management
    path("users/", AdminUserListView.as_view(), name="admin-users"),
    # Admin expert application management
    path(
        "experts/applications/",
        AdminExpertApplicationListView.as_view(),
        name="admin-expert-applications",
    ),
    path(
        "experts/applications/<int:profile_id>/",
        AdminExpertApplicationUpdateView.as_view(),
        name="admin-expert-application-update",
    ),
    # Admin entrepreneur application management
    path(
        "entrepreneurs/applications/",
        AdminEntrepreneurApplicationListView.as_view(),
        name="admin-entrepreneur-applications",
    ),
    path(
        "entrepreneurs/applications/<int:profile_id>/",
        AdminEntrepreneurApplicationUpdateView.as_view(),
        name="admin-entrepreneur-application-update",
    ),
    # Admin advertisement management
    path(
        "ads/",
        AdminAdvertisementListView.as_view(),
        name="admin-advertisements",
    ),
    path(
        "ads/create/",
        AdminAdvertisementCreateView.as_view(),
        name="admin-advertisement-create",
    ),
    path(
        "ads/<int:id>/",
        AdminAdvertisementUpdateView.as_view(),
        name="admin-advertisement-update",
    ),
    path(
        "ads/<int:id>/delete/",
        AdminAdvertisementDeleteView.as_view(),
        name="admin-advertisement-delete",
    ),
    # =====================================================
    # COMPANIES
    # =====================================================
    path("companies/", AdminCompanyListView.as_view(), name="admin-companies-list"),
    path(
        "companies/<uuid:uuid>/",
        AdminCompanyDetailView.as_view(),
        name="admin-company-detail",
    ),
    path(
        "companies/<uuid:uuid>/update/",
        AdminCompanyUpdateView.as_view(),
        name="admin-company-update",
    ),
    path(
        "companies/<uuid:uuid>/delete/",
        AdminCompanyDeleteView.as_view(),
        name="admin-company-delete",
    ),
    # =====================================================
    # MEMBERS
    # =====================================================
    path(
        "companies/<uuid:company_uuid>/members/",
        AdminCompanyMembersView.as_view(),
        name="admin-company-members",
    ),
    path(
        "company-members/<uuid:uuid>/remove/",
        AdminCompanyMemberRemoveView.as_view(),
        name="admin-remove-member",
    ),
    # =====================================================
    # POSTS
    # =====================================================
    path(
        "companies/<uuid:company_uuid>/posts/",
        AdminCompanyPostsView.as_view(),
        name="admin-company-posts",
    ),
    path(
        "company-posts/<uuid:uuid>/delete/",
        AdminCompanyPostDeleteView.as_view(),
        name="admin-company-post-delete",
    ),
    # =====================================================
    # COMPANY SETTINGS
    # =====================================================
    path(
        "company-settings/",
        CompanyPostSettingsView.as_view(),
        name="admin-company-settings",
    ),
]
