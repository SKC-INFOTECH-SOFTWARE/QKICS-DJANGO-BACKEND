"""
PayU hosted-checkout gateway.

Provider-specific details (hash formula, field names, base URL) live ONLY in
this file. The rest of the app talks to it through BasePaymentService, so
switching gateways later means adding a sibling of this class — nothing here
leaks outward.

Docs: PayU "_payment" hosted checkout, SHA-512 request + reverse hash.
"""

import hashlib
import uuid

from django.conf import settings
from django.utils import timezone

from payments.models import Payment
from .base import BasePaymentService


def _sha512(raw: str) -> str:
    return hashlib.sha512(raw.encode("utf-8")).hexdigest().lower()


class PayUPaymentService(BasePaymentService):
    GATEWAY = Payment.GATEWAY_PAYU

    # ------------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------------
    def create_payment(self, *, user, purpose, reference_id, amount):
        # PayU txnid must be unique and <= 25 chars.
        txnid = uuid.uuid4().hex[:24]
        return Payment.objects.create(
            user=user,
            purpose=purpose,
            reference_id=reference_id,
            amount=amount,
            status=Payment.STATUS_INITIATED,
            gateway=self.GATEWAY,
            gateway_order_id=txnid,
        )

    def confirm_payment(self, *, payment, gateway_payment_id=None, raw=None):
        payment.status = Payment.STATUS_SUCCESS
        if gateway_payment_id:
            payment.gateway_payment_id = gateway_payment_id
        payment.gateway_response = raw or {
            "message": "PayU payment successful",
            "confirmed_at": timezone.now().isoformat(),
        }
        payment.save(
            update_fields=["status", "gateway_payment_id", "gateway_response", "updated_at"]
        )
        return payment

    def fail_payment(self, *, payment, reason=None, raw=None):
        payment.status = Payment.STATUS_FAILED
        payment.gateway_response = raw or {
            "message": "PayU payment failed",
            "reason": reason,
            "failed_at": timezone.now().isoformat(),
        }
        payment.save(update_fields=["status", "gateway_response", "updated_at"])
        return payment

    # ------------------------------------------------------------------
    # CHECKOUT
    # ------------------------------------------------------------------
    def start_checkout(self, *, payment, customer, surl, furl):
        key = settings.PAYU_KEY
        salt = settings.PAYU_SALT
        if not key or not salt:
            raise RuntimeError("PAYU_KEY / PAYU_SALT are not configured.")

        txnid = payment.gateway_order_id
        amount = f"{payment.amount:.2f}"
        productinfo = f"{payment.purpose}:{payment.reference_id}"
        firstname = (customer.get("name") or "Customer").strip()[:60]
        email = (customer.get("email") or "").strip()
        phone = (customer.get("phone") or "").strip()

        # udf1 carries our payment uuid so the callback can locate it even if
        # txnid handling ever changes.
        udf1 = str(payment.uuid)
        udf = [udf1, "", "", "", ""]

        # Request hash:
        # key|txnid|amount|productinfo|firstname|email|udf1|...|udf5||||||salt
        hash_seq = [key, txnid, amount, productinfo, firstname, email] + udf
        hash_str = "|".join(hash_seq) + "|||||" + salt
        request_hash = _sha512(hash_str)

        params = {
            "key": key,
            "txnid": txnid,
            "amount": amount,
            "productinfo": productinfo,
            "firstname": firstname,
            "email": email,
            "phone": phone,
            "surl": surl,
            "furl": furl,
            "udf1": udf1,
            "hash": request_hash,
        }
        return {
            "flow": "redirect_post",
            "action_url": f"{settings.PAYU_BASE_URL}/_payment",
            "params": params,
        }

    # ------------------------------------------------------------------
    # CALLBACK VERIFICATION
    # ------------------------------------------------------------------
    def verify_callback(self, *, data):
        """
        `data` = PayU POST-back (form dict). Returns (payment, is_successful).
        Verifies the reverse hash before trusting anything.
        """
        salt = settings.PAYU_SALT
        key = data.get("key", "")
        txnid = data.get("txnid", "")
        amount = data.get("amount", "")
        productinfo = data.get("productinfo", "")
        firstname = data.get("firstname", "")
        email = data.get("email", "")
        status = data.get("status", "")
        received_hash = (data.get("hash") or "").lower()

        udf = [data.get(f"udf{i}", "") for i in range(1, 6)]

        # Reverse hash:
        # salt|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
        reverse_seq = (
            [salt, status]
            + ["", "", "", "", "", ""]
            + list(reversed(udf))
            + [email, firstname, productinfo, amount, txnid, key]
        )
        expected_hash = _sha512("|".join(reverse_seq))

        # Locate our payment (prefer udf1 = payment uuid, fall back to txnid).
        payment = None
        payment_uuid = data.get("udf1")
        if payment_uuid:
            payment = Payment.objects.filter(uuid=payment_uuid).first()
        if payment is None and txnid:
            payment = Payment.objects.filter(gateway_order_id=txnid).first()

        if payment is None:
            return None, False

        if expected_hash != received_hash:
            # Tampered / invalid — do NOT trust the status.
            return payment, False

        is_success = status.lower() == "success"
        return payment, is_success
