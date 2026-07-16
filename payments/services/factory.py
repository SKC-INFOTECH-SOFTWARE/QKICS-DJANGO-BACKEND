"""
Single place that decides which payment gateway is live.

Every view/service obtains its gateway via get_payment_service() — never by
importing a concrete class. To switch gateways: add the new service to
_REGISTRY and set PAYMENT_GATEWAY in the env. Nothing else changes.
"""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .fake import FakePaymentService
from .payu import PayUPaymentService

_REGISTRY = {
    "fake": FakePaymentService,
    "payu": PayUPaymentService,
    # "razorpay": RazorpayPaymentService,   # <- future: one line to add
}


def get_payment_service(name: str = None):
    """
    Return an instance of the configured (or explicitly named) gateway.

    Safety: the "fake" gateway confirms payments without any money moving, so
    it must NEVER run in production. If DEBUG is off and something selects
    fake, we refuse hard rather than silently bypass payment.
    """
    key = (name or settings.PAYMENT_GATEWAY or "payu").lower()

    if key == "fake" and not settings.DEBUG:
        raise ImproperlyConfigured(
            "PAYMENT_GATEWAY='fake' is not allowed when DEBUG=False. "
            "Set PAYMENT_GATEWAY=payu in the production environment."
        )

    try:
        return _REGISTRY[key]()
    except KeyError:
        raise ValueError(
            f"Unknown PAYMENT_GATEWAY '{key}'. "
            f"Available: {', '.join(_REGISTRY)}"
        )
