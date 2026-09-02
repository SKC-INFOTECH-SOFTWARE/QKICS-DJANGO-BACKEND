"""
Email-OTP business logic: issuing (with rate limits) and verifying codes for
registration email verification and password reset.

Kept out of the views so both DRF serializers/views and any future callers
share one hardened path. All user-facing failures return a short reason string
so callers can surface a generic-but-useful message.
"""

from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from users.models import EmailOTP
from users.services.email import send_otp_email


class OTPError(Exception):
    """Raised for OTP issue/verify failures. `code` is a stable machine slug."""

    def __init__(self, message, code="otp_error"):
        super().__init__(message)
        self.message = message
        self.code = code


# ---------------------------------------------------------------------------
# Issuing
# ---------------------------------------------------------------------------
def issue_otp(*, email, purpose):
    """
    Rate-limit, create and email a fresh OTP for (email, purpose).

    Raises OTPError('rate_limited' / 'cooldown') when limits are hit.
    Returns the created EmailOTP instance.
    """
    email = email.strip().lower()
    now = timezone.now()

    recent = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gte=now - timedelta(hours=1),
    )

    # Hourly cap
    max_per_hour = getattr(settings, "OTP_MAX_PER_HOUR", 5)
    if recent.count() >= max_per_hour:
        raise OTPError(
            "Too many code requests. Please try again in an hour.",
            code="rate_limited",
        )

    # Resend cooldown (based on the latest code for this email+purpose)
    cooldown = getattr(settings, "OTP_RESEND_COOLDOWN_SECONDS", 60)
    latest = recent.order_by("-created_at").first()
    if latest and (now - latest.created_at).total_seconds() < cooldown:
        wait = int(cooldown - (now - latest.created_at).total_seconds())
        raise OTPError(
            f"Please wait {wait}s before requesting another code.",
            code="cooldown",
        )

    # Invalidate any earlier un-used codes for this email+purpose so only the
    # newest one can be redeemed.
    recent.filter(is_used=False).update(is_used=True)

    otp, code = EmailOTP.issue(email=email, purpose=purpose)
    send_otp_email(email, code, purpose)
    return otp


# ---------------------------------------------------------------------------
# Verifying
# ---------------------------------------------------------------------------
def _latest_active(email, purpose):
    return (
        EmailOTP.objects.filter(email=email.strip().lower(), purpose=purpose, is_used=False)
        .order_by("-created_at")
        .first()
    )


def verify_otp(*, email, code, purpose, consume=False, mark_verified=False):
    """
    Validate `code` against the newest un-used OTP for (email, purpose).

    - consume=True         -> mark the row is_used (single-use redemption).
    - mark_verified=True   -> stamp verified_at (registration: trust email for
                              a short window before the account is created).

    Returns the EmailOTP on success. Raises OTPError on any failure with a
    stable `code`: 'not_found', 'expired', 'too_many_attempts', 'invalid'.
    """
    otp = _latest_active(email, purpose)
    if otp is None:
        raise OTPError("No active code found. Please request a new one.", code="not_found")

    if otp.is_expired:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise OTPError("This code has expired. Please request a new one.", code="expired")

    max_attempts = getattr(settings, "OTP_MAX_ATTEMPTS", 5)
    if otp.attempts >= max_attempts:
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise OTPError(
            "Too many incorrect attempts. Please request a new code.",
            code="too_many_attempts",
        )

    if not otp.check_code(code):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise OTPError("Incorrect code. Please try again.", code="invalid")

    fields = []
    if mark_verified:
        otp.verified_at = timezone.now()
        fields.append("verified_at")
    if consume:
        otp.is_used = True
        fields.append("is_used")
    if fields:
        otp.save(update_fields=fields)
    return otp


def registration_email_verified(email):
    """Peek (no consume): is there a valid, verified register-OTP in window?"""
    window = getattr(settings, "OTP_VERIFIED_WINDOW_MINUTES", 15)
    cutoff = timezone.now() - timedelta(minutes=window)
    return EmailOTP.objects.filter(
        email=email.strip().lower(),
        purpose=EmailOTP.PURPOSE_REGISTER,
        is_used=False,
        verified_at__isnull=False,
        verified_at__gte=cutoff,
    ).exists()


def consume_verified_registration(email):
    """
    Called by RegisterAPIView: confirm the email was OTP-verified within the
    allowed window, then consume that OTP so it can't be reused.

    Returns True if a valid verified OTP was consumed; False otherwise.
    """
    window = getattr(settings, "OTP_VERIFIED_WINDOW_MINUTES", 15)
    cutoff = timezone.now() - timedelta(minutes=window)
    otp = (
        EmailOTP.objects.filter(
            email=email.strip().lower(),
            purpose=EmailOTP.PURPOSE_REGISTER,
            is_used=False,
            verified_at__isnull=False,
            verified_at__gte=cutoff,
        )
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        return False
    otp.is_used = True
    otp.save(update_fields=["is_used"])
    return True
