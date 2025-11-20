from django.urls import path
from .views import (
    EntrepreneurProfileAPIView,
    ExpertProfileAPIView,
    VerifiedEntrepreneursListAPIView,
    VerifiedExpertsListAPIView,
)

urlpatterns = [
    # Entrepreneur
    path(
        "entrepreneur/profile/",
        EntrepreneurProfileAPIView.as_view(),
        name="entrepreneur-profile",
    ),
    path(
        "entrepreneurs/",
        VerifiedEntrepreneursListAPIView.as_view(),
        name="entrepreneurs-list",
    ),
    # Expert
    path("expert/profile/", ExpertProfileAPIView.as_view(), name="expert-profile"),
    path("experts/", VerifiedExpertsListAPIView.as_view(), name="experts-list"),
]
