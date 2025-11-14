from django.urls import path
from .views import RegisterAPIView, LoginAPIView, UserUpdateAPIView, PasswordChangeAPIView

urlpatterns = [
    path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginAPIView.as_view(), name='login'),
    path('me/update/', UserUpdateAPIView.as_view(), name='user-update'),
    path('me/change-password/', PasswordChangeAPIView.as_view(), name='change-password'),
]