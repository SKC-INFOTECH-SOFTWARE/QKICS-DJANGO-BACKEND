from django.urls import path, include
from .views import (
    SubscriptionPlanListView,
    SubscribeView,
    MySubscriptionView,
)

urlpatterns = [
    path("plans/", SubscriptionPlanListView.as_view(), name="subscription-plans"),
    path("subscribe/", SubscribeView.as_view(), name="subscription-subscribe"),
    path("me/", MySubscriptionView.as_view(), name="my-subscription"),
    path("", include("subscriptions.urls_admin")),
]
