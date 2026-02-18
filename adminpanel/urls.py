from django.urls import path
from .views.users import AdminUserListView

urlpatterns = [
    path("users/", AdminUserListView.as_view(), name="admin-users"),
]