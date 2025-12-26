from django.utils import timezone
from payments.models import Payment
from .base import BasePaymentService


class FakePaymentService(BasePaymentService):
    """
    Fake payment gateway.
    Used for development and testing.
    """

    def create_payment(self, *, user, purpose, reference_id, amount):
        payment = Payment.objects.create(
            user=user,
            purpose=purpose,
            reference_id=reference_id,
            amount=amount,
            status=Payment.STATUS_INITIATED,
            gateway=Payment.GATEWAY_FAKE,
        )
        return payment

    def confirm_payment(self, *, payment):
        payment.status = Payment.STATUS_SUCCESS
        payment.gateway_response = {
            "message": "Fake payment successful",
            "confirmed_at": timezone.now().isoformat(),
        }
        payment.save(update_fields=["status", "gateway_response"])
        return payment

    def fail_payment(self, *, payment, reason=None):
        payment.status = Payment.STATUS_FAILED
        payment.gateway_response = {
            "message": "Fake payment failed",
            "reason": reason,
            "failed_at": timezone.now().isoformat(),
        }
        payment.save(update_fields=["status", "gateway_response"])
        return payment
