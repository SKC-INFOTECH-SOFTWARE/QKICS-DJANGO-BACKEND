from django.urls import path
from .views import FakeBookingPaymentView

urlpatterns = [
    path(
        "fake/booking/",
        FakeBookingPaymentView.as_view(),
        name="fake-booking-payment",
    ),
]
