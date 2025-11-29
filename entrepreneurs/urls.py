from django.urls import path
from .views import (
    EntrepreneurListView,
    EntrepreneurDetailView,
    EntrepreneurProfileSelfView,
    EntrepreneurApplicationSubmitView,
    AdminVerifyEntrepreneurView,
)

urlpatterns = [
    path("", EntrepreneurListView.as_view(), name="entrepreneur-list"),
    path("me/profile/", EntrepreneurProfileSelfView.as_view(), name="entrepreneur-profile-self"),
    path("me/submit/", EntrepreneurApplicationSubmitView.as_view(), name="entrepreneur-submit"),
    path("admin/verify/<int:profile_id>/", AdminVerifyEntrepreneurView.as_view(), name="admin-verify-entrepreneur"),
    path("<str:username>/", EntrepreneurDetailView.as_view(), name="entrepreneur-detail"),
]