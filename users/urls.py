from django.urls import path

from .views import (
    RegisterAPIView,
    LoginAPIView,
    GetMyProfileAPIView,
    UserUpdateAPIView,
    PasswordChangeAPIView,
    UsernameCheckAPIView,
    EmailCheckAPIView,
    PhoneCheckAPIView,
    LogoutAPIView,
    AdminUserListAPIView,
    CookieTokenRefreshView,
    AdminCreateUserAPIView,
    UnifiedPublicProfileAPIView,
)

urlpatterns = [
    # Authentication
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    
    # Public Profile (Unified)
    path("profiles/<str:username>/", UnifiedPublicProfileAPIView.as_view(), name="public-profile",),

    # User Profile Management
    path("me/", GetMyProfileAPIView.as_view(), name="my-profile"),
    path("me/update/", UserUpdateAPIView.as_view(), name="user-update"),
    path("me/change-password/", PasswordChangeAPIView.as_view(), name="change-password"),

    # Availability checks
    path("check-username/", UsernameCheckAPIView.as_view(), name="check-username"),
    path("check-email/", EmailCheckAPIView.as_view(), name="check-email"),
    path("check-phone/", PhoneCheckAPIView.as_view(), name="check-phone"),

    # Admin APIs (only listing users now)
    path("admin/users/", AdminUserListAPIView.as_view(), name="admin-user-list"),
    path("admin/create/", AdminCreateUserAPIView.as_view(), name="admin-create-user"),

    # Logout
    path("logout/", LogoutAPIView.as_view(), name="logout"),
]
