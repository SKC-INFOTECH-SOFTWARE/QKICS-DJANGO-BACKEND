"""
Delivering meeting invites: an in-app/push notification for registered users
(via the external notification service) and a branded email with the join link.
"""
import logging

logger = logging.getLogger(__name__)


def _format_when(meeting):
    from django.utils import timezone

    if not meeting.scheduled_start:
        return "Starting now"
    local = timezone.localtime(meeting.scheduled_start)
    return local.strftime("%d %b %Y, %I:%M %p")


def send_invite_email(*, to, meeting, link, invitee_name=""):
    """Queue a meeting-invite email. Never raises — failures are logged."""
    from users.services.email import _async, _send, _wrap

    when = _format_when(meeting)
    greeting = f"Hi {invitee_name}," if invitee_name else "Hi,"
    host = meeting.host.get_full_name() or meeting.host.username

    inner = f"""
      <p style="margin:0 0 14px;font-size:14px;line-height:1.6;">{greeting}</p>
      <p style="margin:0 0 18px;font-size:14px;line-height:1.6;">
        <strong>{host}</strong> has invited you to a video meeting on Qkics.
      </p>
      <div style="background:#f7f7f9;border-radius:12px;padding:16px;margin-bottom:20px;">
        <p style="margin:0 0 6px;font-size:16px;font-weight:700;">{meeting.title}</p>
        <p style="margin:0;font-size:13px;color:#555;">{when}</p>
      </div>
      <p style="margin:0 0 20px;text-align:center;">
        <a href="{link}" style="display:inline-block;background:#e11d2a;color:#ffffff;
           text-decoration:none;padding:13px 28px;border-radius:10px;font-weight:700;font-size:14px;">
          Join Meeting
        </a>
      </p>
      <p style="margin:0 0 6px;font-size:12px;color:#777;line-height:1.6;">
        Or paste this link into your browser:<br>
        <span style="color:#e11d2a;word-break:break-all;">{link}</span>
      </p>
      <p style="margin:14px 0 0;font-size:12px;color:#777;line-height:1.6;">
        This meeting is recorded. Recordings are kept for
        {meeting.RECORDING_RETENTION_DAYS} days and then permanently deleted.
      </p>
    """

    text_body = (
        f"{greeting}\n\n{host} has invited you to a video meeting on Qkics.\n\n"
        f"{meeting.title}\n{when}\n\nJoin: {link}\n\n"
        f"This meeting is recorded; recordings are deleted after "
        f"{meeting.RECORDING_RETENTION_DAYS} days.\n"
    )

    _async(
        _send,
        to=to,
        subject=f"Meeting invite: {meeting.title}",
        text_body=text_body,
        html_body=_wrap("You're invited to a meeting", inner),
    )


def notify_invited_user(*, user, meeting, link):
    """In-app + push notification for a registered invitee."""
    try:
        from notifications.services.client import send_notification

        send_notification(
            event="MEETING_INVITE",
            user_id=str(user.id),
            title=f"Meeting invite: {meeting.title}",
            body=f"{_format_when(meeting)} — tap to join.",
            channels=["IN_APP", "PUSH"],
            user_email=user.email or None,
            data={
                "meeting_id": str(meeting.id),
                "invite_token": meeting.invite_token,
                "link": link,
            },
        )
    except Exception as e:
        logger.error("notify_invited_user failed [meeting=%s]: %s", meeting.id, e)
