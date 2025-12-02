from django.urls import path
from .views import (
    InvestorListView, InvestorDetailView,
    AdminCreateInvestorView, AdminVerifyInvestorView,
    IndustryListView, StartupStageListView, InvestorProfileSelfView, AdminCreateInvestorProfileView
)

urlpatterns = [
    path("", InvestorListView.as_view(), name="investor-list"),
    path("industries/", IndustryListView.as_view(), name="industry-list"),
    path("stages/", StartupStageListView.as_view(), name="stage-list"),
    path("admin/create/", AdminCreateInvestorView.as_view(), name="admin-create-investor"),
    path("admin/verify/<int:investor_id>/", AdminVerifyInvestorView.as_view(), name="admin-verify-investor"),
    path("<str:username>/", InvestorDetailView.as_view(), name="investor-detail"),
    path("me/profile/", InvestorProfileSelfView.as_view(), name="investor-profile-self"),
    
    path("admin/create-profile/", AdminCreateInvestorProfileView.as_view(), name="admin-create-investor-profile"),
]