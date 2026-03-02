from django.urls import path
from ads.views import PublicActiveAdvertisementView

urlpatterns = [
    path(
        "active/",
        PublicActiveAdvertisementView.as_view(),
        name="public-active-ads",
    ),
]
