from django.urls import path

from .views import (
    # Public
    ExpertListView,
    ExpertDetailView,

    # Self profile
    ExpertProfileSelfView,
    ExpertApplicationSubmitView,

    # Admin
    AdminVerifyExpertView,

    # Experiences
    ExperienceCreateView,
    ExperienceDetailView,

    # Education
    EducationCreateView,
    EducationDetailView,

    # Certifications
    CertificationCreateView,
    CertificationDetailView,

    # Honors & Awards
    HonorAwardCreateView,
    HonorAwardDetailView,
)

urlpatterns = [
    # ===========================
    # PUBLIC ENDPOINTS
    # ===========================
    path("", ExpertListView.as_view(), name="expert-list"),
    path("<str:username>/", ExpertDetailView.as_view(), name="expert-detail"),

    # ===========================
    # SELF PROFILE (Authenticated Expert User)
    # ===========================
    path("me/profile/", ExpertProfileSelfView.as_view(), name="expert-profile-self"),
    path("me/submit/", ExpertApplicationSubmitView.as_view(), name="expert-submit-application"),

    # ===========================
    # ADMIN VERIFY
    # ===========================
    path("admin/verify/<int:profile_id>/", AdminVerifyExpertView.as_view(), name="admin-verify-expert"),

    # ===========================
    # EXPERIENCE CRUD
    # ===========================
    path("experience/", ExperienceCreateView.as_view(), name="experience-create"),
    path("experience/<int:pk>/", ExperienceDetailView.as_view(), name="experience-detail"),

    # ===========================
    # EDUCATION CRUD
    # ===========================
    path("education/", EducationCreateView.as_view(), name="education-create"),
    path("education/<int:pk>/", EducationDetailView.as_view(), name="education-detail"),

    # ===========================
    # CERTIFICATION CRUD
    # ===========================
    path("certifications/", CertificationCreateView.as_view(), name="certification-create"),
    path("certifications/<int:pk>/", CertificationDetailView.as_view(), name="certification-detail"),

    # ===========================
    # HONORS & AWARDS CRUD
    # ===========================
    path("honors/", HonorAwardCreateView.as_view(), name="honor-create"),
    path("honors/<int:pk>/", HonorAwardDetailView.as_view(), name="honor-detail"),
]
