from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from bookings.models import Booking
from payments.models import Payment
from payments.serializers import (
    FakeBookingPaymentSerializer,
    InitiatePaymentSerializer,
    PaymentSerializer,
)
from payments.services.factory import get_payment_service
from payments.services.dispatch import fulfill_payment
from payments.services.payu import PayUPaymentService
from bookings.services.confirm_booking import confirm_booking_after_payment
from subscriptions.models import SubscriptionPlan, UserSubscription
from subscriptions.serializers import UserSubscriptionSerializer
from django.utils import timezone


# ============================================================
# HELPERS
# ============================================================

BOOKING_PAYABLE_STATES = (
    Booking.STATUS_PENDING,
    Booking.STATUS_AWAITING_PAYMENT,
)


def _customer_from_user(user):
    return {
        "name": (user.get_full_name() or user.username or "Customer"),
        "email": user.email or "",
        "phone": getattr(user, "phone", "") or "",
    }


def _booking_result(booking):
    """Domain payload the frontend needs right after a booking is confirmed."""
    booking.refresh_from_db()
    call_room_id = None
    try:
        if booking.is_batch:
            call_room_id = str(booking.slot.call_room.id)
        else:
            call_room_id = str(booking.call_room.id)
    except Exception:
        pass
    return {
        "booking_id": str(booking.uuid),
        "chat_room_id": booking.chat_room_id,
        "call_room_id": call_room_id,
    }


# ============================================================
# GENERIC: INITIATE PAYMENT (any gateway, any purpose)
# ============================================================


class InitiatePaymentView(APIView):
    """
    POST /v1/payments/initiate/

    Body: {purpose: BOOKING|SUBSCRIPTION, booking_id?|plan_uuid?}

    Returns a gateway-neutral instruction:
      - instant gateways      -> {"flow":"instant", "payment":..., "result":...}
      - hosted-checkout ones  -> {"flow":"redirect_post", "checkout":{action_url, params}}

    The web/app client just follows `flow` — it never knows which gateway ran.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        purpose = serializer.validated_data["purpose"]

        # -------- resolve reference + amount (SERVER-SIDE, never trust client) --------
        if purpose == Payment.PURPOSE_BOOKING:
            booking = get_object_or_404(
                Booking,
                uuid=serializer.validated_data["booking_id"],
                user=request.user,
            )
            if booking.status not in BOOKING_PAYABLE_STATES:
                return Response(
                    {"message": f"Cannot pay for booking in {booking.status} state"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            reference_id = booking.uuid
            amount = booking.price
        else:  # SUBSCRIPTION
            try:
                plan = SubscriptionPlan.objects.get(
                    uuid=serializer.validated_data["plan_uuid"], is_active=True
                )
            except SubscriptionPlan.DoesNotExist:
                return Response(
                    {"message": "Invalid subscription plan"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            if UserSubscription.objects.filter(
                user=request.user, is_active=True, end_date__gt=timezone.now()
            ).exists():
                return Response(
                    {"message": "You already have an active subscription"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            reference_id = plan.uuid
            amount = plan.price

        # -------- create payment via the configured gateway --------
        service = get_payment_service()
        payment = service.create_payment(
            user=request.user,
            purpose=purpose,
            reference_id=reference_id,
            amount=amount,
        )

        surl = request.build_absolute_uri(reverse("payu-callback-success"))
        furl = request.build_absolute_uri(reverse("payu-callback-failure"))

        instruction = service.start_checkout(
            payment=payment,
            customer=_customer_from_user(request.user),
            surl=surl,
            furl=furl,
        )

        # -------- instant gateways (fake): confirm + fulfil right away --------
        if instruction.get("flow") == "instant":
            service.confirm_payment(payment=payment)
            fulfill_payment(payment)
            result = None
            if purpose == Payment.PURPOSE_BOOKING:
                result = _booking_result(booking)
            else:
                sub = UserSubscription.objects.filter(
                    user=request.user, is_active=True
                ).order_by("-created_at").first()
                result = UserSubscriptionSerializer(sub).data if sub else None
            return Response(
                {
                    "flow": "instant",
                    "payment": PaymentSerializer(payment).data,
                    "result": result,
                },
                status=status.HTTP_201_CREATED,
            )

        # -------- hosted checkout (payu): hand params to the client --------
        return Response(
            {
                "flow": instruction["flow"],
                "payment": PaymentSerializer(payment).data,
                "checkout": {
                    "action_url": instruction["action_url"],
                    "params": instruction["params"],
                },
            },
            status=status.HTTP_200_OK,
        )


# ============================================================
# GENERIC: PAYMENT STATUS (poll)
# ============================================================


class PaymentStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uuid):
        payment = get_object_or_404(Payment, uuid=uuid, user=request.user)
        data = PaymentSerializer(payment).data
        if payment.purpose == Payment.PURPOSE_BOOKING and payment.status == Payment.STATUS_SUCCESS:
            booking = Booking.objects.filter(uuid=payment.reference_id).first()
            if booking:
                data["result"] = _booking_result(booking)
        return Response(data, status=status.HTTP_200_OK)


# ============================================================
# PayU-SPECIFIC CALLBACKS (browser redirect POST from PayU)
# ============================================================


def _handle_payu_return(request):
    """Verify PayU's POST-back, fulfil if valid, return (payment, ok)."""
    data = request.POST.dict()
    service = PayUPaymentService()
    payment, ok = service.verify_callback(data=data)

    if payment is None:
        return None, False

    if ok:
        if payment.status != Payment.STATUS_SUCCESS:
            service.confirm_payment(
                payment=payment,
                gateway_payment_id=data.get("mihpayid"),
                raw=data,
            )
            fulfill_payment(payment)
    else:
        if payment.status == Payment.STATUS_INITIATED:
            service.fail_payment(payment=payment, reason=data.get("status"), raw=data)
    return payment, ok


@method_decorator(csrf_exempt, name="dispatch")
class PayUCallbackSuccessView(APIView):
    """PayU `surl`. Verifies, fulfils, redirects browser to the frontend."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        payment, ok = _handle_payu_return(request)
        return _redirect_to_frontend(payment, ok)

    # PayU may issue a GET on some flows.
    def get(self, request):
        return _redirect_to_frontend(None, False)


@method_decorator(csrf_exempt, name="dispatch")
class PayUCallbackFailureView(APIView):
    """PayU `furl`."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        payment, ok = _handle_payu_return(request)
        return _redirect_to_frontend(payment, ok)

    def get(self, request):
        return _redirect_to_frontend(None, False)


@method_decorator(csrf_exempt, name="dispatch")
class PayUWebhookView(APIView):
    """
    Optional PayU server-to-server webhook. Same verification + idempotent
    fulfilment as the browser callback; returns plain 200 to PayU.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        _handle_payu_return(request)
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


def _redirect_to_frontend(payment, ok):
    state = "success" if ok else "failed"
    pid = str(payment.uuid) if payment else ""
    url = f"{settings.FRONTEND_URL}/payment/result?status={state}&payment={pid}"
    return redirect(url)


# ============================================================
# LEGACY: FAKE BOOKING PAYMENT (kept for backward compatibility)
# ============================================================


class FakeBookingPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = FakeBookingPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        booking_id = serializer.validated_data["booking_id"]

        booking = get_object_or_404(
            Booking,
            uuid=booking_id,
            user=request.user,
        )

        # FAKE: set directly to CONFIRMED — no approval or payment step needed
        if booking.status not in (Booking.STATUS_PENDING, Booking.STATUS_AWAITING_PAYMENT):
            return Response(
                {"message": f"Cannot pay for booking in {booking.status} state"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payment_service = get_payment_service("fake")

        payment = payment_service.create_payment(
            user=request.user,
            purpose=Payment.PURPOSE_BOOKING,
            reference_id=booking.uuid,
            amount=booking.price,
        )

        payment = payment_service.confirm_payment(payment=payment)

        confirm_booking_after_payment(payment=payment)

        booking.refresh_from_db()

        call_room_id = None
        try:
            if booking.is_batch:
                call_room_id = str(booking.slot.call_room.id)
            else:
                call_room_id = str(booking.call_room.id)
        except Exception:
            pass

        return Response(
            {
                "payment": PaymentSerializer(payment).data,
                "booking_id": str(booking.uuid),
                "chat_room_id": booking.chat_room_id,
                "call_room_id": call_room_id,
                "status": "BOOKING_CONFIRMED_AND_CHAT_CREATED",
            },
            status=status.HTTP_201_CREATED,
        )
