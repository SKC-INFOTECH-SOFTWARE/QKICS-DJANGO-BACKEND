from django.urls import path
from .views import (
    RegisterAPIView,
    LoginAPIView,
    UserUpdateAPIView,
    PasswordChangeAPIView,
    UsernameCheckAPIView,
    EmailCheckAPIView,
    PhoneCheckAPIView,
    LogoutAPIView,
)

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("me/update/", UserUpdateAPIView.as_view(), name="user-update"),
    path(
        "me/change-password/", PasswordChangeAPIView.as_view(), name="change-password"
    ),
    path("check-username/", UsernameCheckAPIView.as_view(), name="check-username"),
    path("check-email/", EmailCheckAPIView.as_view(), name="check-email"),
    path("check-phone/", PhoneCheckAPIView.as_view(), name="check-phone"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
]
