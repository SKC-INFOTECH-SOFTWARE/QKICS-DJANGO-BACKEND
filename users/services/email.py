"""
Transactional emails sent directly via Django's email backend (SMTP in prod,
console in dev). Kept separate from the external notification microservice
(notifications/services) because OTP delivery is security-critical and needs
our own reliable, branded templates.

All sends run in a background thread so the request is never blocked; failures
are logged, not raised.
"""

import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)

BRAND = "Qkics"


def _async(fn, *args, **kwargs):
    def wrapper(*a, **kw):
        try:
            fn(*a, **kw)
        except Exception:
            import traceback

            logger.error("Email thread error: %s", traceback.format_exc())

    threading.Thread(target=wrapper, args=args, kwargs=kwargs, daemon=True).start()


def _send(*, to, subject, text_body, html_body):
    """Blocking send (called inside a thread)."""
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    msg = EmailMultiAlternatives(subject, text_body, from_email, [to])
    msg.attach_alternative(html_body, "text/html")
    msg.send(fail_silently=False)


# ---------------------------------------------------------------------------
# Shared HTML shell
# ---------------------------------------------------------------------------
def _wrap(title, inner):
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;background:#f5f5f7;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a;">
    <div style="max-width:480px;margin:0 auto;padding:32px 16px;">
      <div style="text-align:center;margin-bottom:20px;">
        <span style="font-size:22px;font-weight:800;color:#e11d2a;letter-spacing:-0.5px;">{BRAND}</span>
      </div>
      <div style="background:#ffffff;border-radius:16px;padding:28px 24px;border:1px solid #ececec;">
        <h1 style="margin:0 0 12px;font-size:19px;font-weight:800;">{title}</h1>
        {inner}
      </div>
      <p style="text-align:center;color:#9a9a9a;font-size:12px;margin-top:18px;">
        © {BRAND}. This is an automated message — please do not reply.
      </p>
    </div>
  </body>
</html>"""


def _otp_block(code):
    return f"""\
<div style="text-align:center;margin:22px 0;">
  <div style="display:inline-block;background:#fff0f1;border:1px solid #ffd5d8;border-radius:12px;
              padding:14px 26px;font-size:30px;font-weight:800;letter-spacing:8px;color:#e11d2a;">
    {code}
  </div>
</div>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def send_otp_email(email, code, purpose):
    """
    OTP for registration email verification (purpose='register') or password
    reset (purpose='reset').
    """
    exp = getattr(settings, "OTP_EXP_MINUTES", 10)

    if purpose == "register":
        subject = f"{BRAND} — Verify your email"
        lead = (
            "Use the code below to verify your email and finish creating your "
            f"{BRAND} account."
        )
    else:
        subject = f"{BRAND} — Password reset code"
        lead = (
            "We received a request to reset your password. Use the code below "
            "to continue. If you didn't request this, you can safely ignore "
            "this email."
        )

    inner = (
        f'<p style="margin:0 0 4px;font-size:14px;line-height:1.5;">{lead}</p>'
        + _otp_block(code)
        + f'<p style="margin:0;color:#6b7280;font-size:13px;">This code expires in '
        f"{exp} minutes. Never share it with anyone.</p>"
    )
    html_body = _wrap(subject.split("— ")[-1], inner)
    text_body = f"{lead}\n\nYour {BRAND} code: {code}\n\nExpires in {exp} minutes. Do not share it."

    _async(_send, to=email, subject=subject, text_body=text_body, html_body=html_body)


def send_welcome_email(user):
    """Sent right after an account is successfully created."""
    name = user.get_full_name() or user.username
    subject = f"Welcome to {BRAND}! 🎉"
    inner = (
        f'<p style="margin:0 0 10px;font-size:14px;line-height:1.6;">Hi {name},</p>'
        f'<p style="margin:0 0 10px;font-size:14px;line-height:1.6;">'
        f"You have successfully registered in <strong>{BRAND}</strong>. Your "
        "account is ready — explore experts, entrepreneurs and investors, book "
        "consultations, and join the community.</p>"
        f'<p style="margin:0;font-size:14px;line-height:1.6;">Welcome aboard!</p>'
    )
    html_body = _wrap(f"Welcome to {BRAND}", inner)
    text_body = (
        f"Hi {name},\n\nYou have successfully registered in {BRAND}. "
        "Your account is ready.\n\nWelcome aboard!"
    )
    _async(_send, to=user.email, subject=subject, text_body=text_body, html_body=html_body)
