from django.urls import path
from .views import (
    FakeBookingPaymentView,
    InitiatePaymentView,
    PaymentStatusView,
    PayUCallbackSuccessView,
    PayUCallbackFailureView,
    PayUWebhookView,
)

urlpatterns = [
    # Gateway-agnostic
    path("initiate/", InitiatePaymentView.as_view(), name="payment-initiate"),
    path("status/<uuid:uuid>/", PaymentStatusView.as_view(), name="payment-status"),

    # PayU callbacks (browser redirect POST) + webhook (server-to-server)
    path("payu/callback/success/", PayUCallbackSuccessView.as_view(), name="payu-callback-success"),
    path("payu/callback/failure/", PayUCallbackFailureView.as_view(), name="payu-callback-failure"),
    path("payu/webhook/", PayUWebhookView.as_view(), name="payu-webhook"),

    # Legacy
    path("fake/booking/", FakeBookingPaymentView.as_view(), name="fake-booking-payment"),
]
