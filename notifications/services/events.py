import threading
from .client import send_notification


def _async(fn, *args, **kwargs):
    def wrapper(*a, **kw):
        from django import db
        db.connection.close()  # force a fresh connection in this thread
        try:
            fn(*a, **kw)
        except Exception:
            import traceback, logging
            logging.getLogger(__name__).error(
                "Notification thread error: %s", traceback.format_exc()
            )
    t = threading.Thread(target=wrapper, args=args, kwargs=kwargs, daemon=True)
    t.start()


# ============================================================
# BOOKING NOTIFICATIONS
# ============================================================


def notify_booking_created(booking):
    """
    Sent to the EXPERT when a user creates a new booking request.
    """
    expert = booking.expert
    user = booking.user

    def _send():
        send_notification(
            event="BOOKING_REQUEST_RECEIVED",
            user_id=expert.id,
            user_email=expert.email,
            title="New Booking Request",
            body=(
                f"{user.get_full_name() or user.username} has requested a session "
                f"on {booking.start_datetime.strftime('%d %b %Y at %H:%M')}."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "userId": str(user.id),
                "userName": user.get_full_name() or user.username,
                "startDatetime": booking.start_datetime.isoformat(),
            },
        )

    _async(_send)


def notify_booking_approved(booking):
    """
    Sent to the USER when the expert approves the booking (PENDING → AWAITING_PAYMENT).
    """
    user = booking.user
    expert = booking.expert

    def _send():
        send_notification(
            event="BOOKING_APPROVED",
            user_id=user.id,
            user_email=user.email,
            title="Booking Approved — Complete Payment",
            body=(
                f"Your session with {expert.get_full_name() or expert.username} on "
                f"{booking.start_datetime.strftime('%d %b %Y at %H:%M')} has been approved. "
                "Please complete payment to confirm your booking."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "expertId": str(expert.id),
                "expertName": expert.get_full_name() or expert.username,
            },
        )

    _async(_send)


def notify_booking_declined(booking):
    """
    Sent to the USER when the expert declines the booking.
    """
    user = booking.user
    expert = booking.expert

    def _send():
        send_notification(
            event="BOOKING_DECLINED",
            user_id=user.id,
            user_email=user.email,
            title="Booking Declined",
            body=(
                f"Your booking request with {expert.get_full_name() or expert.username} "
                f"on {booking.start_datetime.strftime('%d %b %Y at %H:%M')} was declined."
                + (
                    f" Reason: {booking.decline_reason}"
                    if booking.decline_reason
                    else ""
                )
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "declineReason": booking.decline_reason or "",
            },
        )

    _async(_send)


def notify_booking_confirmed(booking):
    """
    Sent to BOTH user and expert after payment succeeds and booking is CONFIRMED.
    Chat room is now open.
    """
    user = booking.user
    expert = booking.expert

    def _send():
        # Notify user
        send_notification(
            event="BOOKING_CONFIRMED",
            user_id=user.id,
            user_email=user.email,
            title="Booking Confirmed!",
            body=(
                f"Your session with {expert.get_full_name() or expert.username} on "
                f"{booking.start_datetime.strftime('%d %b %Y at %H:%M')} is confirmed. "
                "Your chat room is now open."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "chatRoomId": (
                    str(booking.chat_room_id) if booking.chat_room_id else None
                ),
                "expertName": expert.get_full_name() or expert.username,
            },
        )

        # Notify expert
        send_notification(
            event="BOOKING_CONFIRMED_EXPERT",
            user_id=expert.id,
            user_email=expert.email,
            title="Booking Confirmed — Session Paid",
            body=(
                f"Payment received! Your session with {user.get_full_name() or user.username} on "
                f"{booking.start_datetime.strftime('%d %b %Y at %H:%M')} is confirmed."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "chatRoomId": (
                    str(booking.chat_room_id) if booking.chat_room_id else None
                ),
                "userName": user.get_full_name() or user.username,
            },
        )

    _async(_send)


def notify_booking_cancelled(booking, cancelled_by):
    """
    Sent to the OTHER party when a booking is cancelled.
    cancelled_by: User object (the one who cancelled)
    """
    other_party = booking.expert if cancelled_by == booking.user else booking.user

    def _send():
        send_notification(
            event="BOOKING_CANCELLED",
            user_id=other_party.id,
            user_email=other_party.email,
            title="Booking Cancelled",
            body=(
                f"The booking on {booking.start_datetime.strftime('%d %b %Y at %H:%M')} "
                f"was cancelled by {cancelled_by.get_full_name() or cancelled_by.username}."
                + (
                    f" Reason: {booking.cancellation_reason}"
                    if booking.cancellation_reason
                    else ""
                )
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "cancelledBy": str(cancelled_by.id),
                "cancellationReason": booking.cancellation_reason or "",
            },
        )

    _async(_send)


def notify_booking_completed(booking):
    """
    Sent to the USER when a session is marked as completed.
    Also notifies expert as a courtesy.
    """
    user = booking.user
    expert = booking.expert

    def _send():
        # Notify user
        send_notification(
            event="BOOKING_COMPLETED",
            user_id=user.id,
            user_email=user.email,
            title="Session Completed",
            body=(
                f"Your session with {expert.get_full_name() or expert.username} is complete. "
                "We hope it was valuable!"
            ),
            channels=["IN_APP", "PUSH"],
            data={"bookingId": str(booking.uuid)},
        )

        # Notify expert
        send_notification(
            event="BOOKING_COMPLETED_EXPERT",
            user_id=expert.id,
            user_email=expert.email,
            title="Session Marked as Completed",
            body=(
                f"Your session with {user.get_full_name() or user.username} "
                f"on {booking.start_datetime.strftime('%d %b %Y at %H:%M')} has been completed."
            ),
            channels=["IN_APP", "PUSH"],
            data={"bookingId": str(booking.uuid)},
        )

    _async(_send)


def notify_booking_expired(booking):
    """
    Sent to the USER when a booking expires without action.
    """
    user = booking.user

    def _send():
        send_notification(
            event="BOOKING_EXPIRED",
            user_id=user.id,
            user_email=user.email,
            title="Booking Expired",
            body=(
                f"Your booking on {booking.start_datetime.strftime('%d %b %Y at %H:%M')} "
                "has expired because no action was taken in time."
            ),
            channels=["IN_APP", "PUSH"],
            data={"bookingId": str(booking.uuid)},
        )

    _async(_send)


def notify_booking_payment_failed(booking):
    """
    Sent to the USER when payment fails for a booking.
    """
    user = booking.user

    def _send():
        send_notification(
            event="BOOKING_PAYMENT_FAILED",
            user_id=user.id,
            user_email=user.email,
            title="Payment Failed",
            body=(
                f"Payment for your booking on "
                f"{booking.start_datetime.strftime('%d %b %Y at %H:%M')} failed. "
                "Please try again."
            ),
            channels=["IN_APP", "PUSH"],
            data={"bookingId": str(booking.uuid)},
        )

    _async(_send)


# ============================================================
# INVESTOR BOOKING NOTIFICATIONS
# ============================================================


def notify_investor_booking_created(booking):
    """
    Sent to the INVESTOR when a user books their consultation slot.
    """
    investor = booking.investor
    user = booking.user

    def _send():
        send_notification(
            event="INVESTOR_BOOKING_CREATED",
            user_id=investor.id,
            user_email=investor.email,
            title="New Consultation Request",
            body=(
                f"{user.get_full_name() or user.username} has booked a consultation "
                f"on {booking.start_datetime.strftime('%d %b %Y at %H:%M')}."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "userId": str(user.id),
                "userName": user.get_full_name() or user.username,
                "startDatetime": booking.start_datetime.isoformat(),
            },
        )

    _async(_send)


def notify_investor_booking_confirmed(booking):
    """
    Sent to the USER when their investor consultation booking is confirmed.
    Chat room is now open.
    """
    user = booking.user
    investor = booking.investor

    def _send():
        # Notify user
        send_notification(
            event="INVESTOR_BOOKING_CONFIRMED",
            user_id=user.id,
            user_email=user.email,
            title="Consultation Confirmed!",
            body=(
                f"Your consultation with {investor.get_full_name() or investor.username} "
                f"on {booking.start_datetime.strftime('%d %b %Y at %H:%M')} is confirmed. "
                "Your chat room is now open."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "bookingId": str(booking.uuid),
                "chatRoomId": (
                    str(booking.chat_room_id) if booking.chat_room_id else None
                ),
                "investorName": investor.get_full_name() or investor.username,
            },
        )

    _async(_send)


# ============================================================
# EXPERT APPLICATION NOTIFICATIONS
# ============================================================


def notify_expert_application_approved(expert_profile):
    """Sent to the expert when their application is approved by admin."""
    user = expert_profile.user

    def _send():
        send_notification(
            event="EXPERT_APPLICATION_APPROVED",
            user_id=user.id,
            user_email=user.email,
            title="Expert Application Approved 🎉",
            body=(
                "Congratulations! Your expert application has been approved. "
                "You can now create slots and start accepting bookings."
            ),
            channels=["IN_APP", "PUSH"],
            data={"expertProfileId": expert_profile.id},
        )

    _async(_send)


def notify_expert_application_rejected(expert_profile):
    """Sent to the expert when their application is rejected by admin."""
    user = expert_profile.user

    def _send():
        send_notification(
            event="EXPERT_APPLICATION_REJECTED",
            user_id=user.id,
            user_email=user.email,
            title="Expert Application Update",
            body=(
                "Your expert application was not approved at this time."
                + (
                    f" Note: {expert_profile.admin_review_note}"
                    if expert_profile.admin_review_note
                    else ""
                )
            ),
            channels=["IN_APP", "PUSH"],
            data={"expertProfileId": expert_profile.id},
        )

    _async(_send)


# ============================================================
# ENTREPRENEUR APPLICATION NOTIFICATIONS
# ============================================================


def notify_entrepreneur_application_approved(entrepreneur_profile):
    """Sent to the entrepreneur when their application is approved by admin."""
    user = entrepreneur_profile.user

    def _send():
        send_notification(
            event="ENTREPRENEUR_APPLICATION_APPROVED",
            user_id=user.id,
            user_email=user.email,
            title="Entrepreneur Application Approved 🎉",
            body=(
                f"Congratulations! Your startup '{entrepreneur_profile.startup_name}' "
                "has been approved and is now listed on the platform."
            ),
            channels=["IN_APP", "PUSH"],
            data={"entrepreneurProfileId": entrepreneur_profile.id},
        )

    _async(_send)


def notify_entrepreneur_application_rejected(entrepreneur_profile):
    """Sent to the entrepreneur when their application is rejected by admin."""
    user = entrepreneur_profile.user

    def _send():
        send_notification(
            event="ENTREPRENEUR_APPLICATION_REJECTED",
            user_id=user.id,
            user_email=user.email,
            title="Entrepreneur Application Update",
            body=(
                f"Your application for '{entrepreneur_profile.startup_name}' was not approved."
                + (
                    f" Note: {entrepreneur_profile.admin_review_note}"
                    if entrepreneur_profile.admin_review_note
                    else ""
                )
            ),
            channels=["IN_APP", "PUSH"],
            data={"entrepreneurProfileId": entrepreneur_profile.id},
        )

    _async(_send)


# ============================================================
# INVESTOR APPLICATION NOTIFICATIONS
# ============================================================


def notify_investor_application_approved(investor):
    """Sent to the investor when their profile is approved by admin."""
    user = investor.user

    def _send():
        send_notification(
            event="INVESTOR_APPLICATION_APPROVED",
            user_id=user.id,
            user_email=user.email,
            title="Investor Profile Approved 🎉",
            body=(
                f"Congratulations! Your investor profile '{investor.display_name}' "
                "has been approved. You are now listed on the platform."
            ),
            channels=["IN_APP", "PUSH"],
            data={"investorId": investor.id},
        )

    _async(_send)


def notify_investor_application_rejected(investor):
    """Sent to the investor when their profile is rejected by admin."""
    user = investor.user

    def _send():
        send_notification(
            event="INVESTOR_APPLICATION_REJECTED",
            user_id=user.id,
            user_email=user.email,
            title="Investor Profile Update",
            body="Your investor profile application was not approved at this time.",
            channels=["IN_APP", "PUSH"],
            data={"investorId": investor.id},
        )

    _async(_send)


# ============================================================
# COMPANY NOTIFICATIONS
# ============================================================


def notify_company_approved(company):
    """Sent to the company owner when admin approves the company."""
    owner = company.owner

    def _send():
        send_notification(
            event="COMPANY_APPROVED",
            user_id=owner.id,
            user_email=owner.email,
            title="Company Approved! 🎉",
            body=(
                f"Your company '{company.name}' has been approved "
                "and is now publicly listed on the platform."
            ),
            channels=["IN_APP", "PUSH"],
            data={"companyId": str(company.id), "companyName": company.name},
        )

    _async(_send)


def notify_company_rejected(company):
    """Sent to the company owner when admin rejects the company."""
    owner = company.owner

    def _send():
        send_notification(
            event="COMPANY_REJECTED",
            user_id=owner.id,
            user_email=owner.email,
            title="Company Application Update",
            body=(
                f"Your company '{company.name}' was not approved at this time. "
                "Please review your details and reapply."
            ),
            channels=["IN_APP", "PUSH"],
            data={"companyId": str(company.id), "companyName": company.name},
        )

    _async(_send)


def notify_company_member_added(company, added_user):
    """Sent to a user when they are added as an editor to a company."""

    def _send():
        send_notification(
            event="COMPANY_MEMBER_ADDED",
            user_id=added_user.id,
            user_email=added_user.email,
            title="Added to Company",
            body=(
                f"You have been added as an editor to '{company.name}'. "
                "You can now create and manage posts for this company."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "companyId": str(company.id),
                "companyName": company.name,
            },
        )

    _async(_send)


def notify_company_member_removed(company, removed_user):
    """Sent to a user when they are removed from a company."""

    def _send():
        send_notification(
            event="COMPANY_MEMBER_REMOVED",
            user_id=removed_user.id,
            user_email=removed_user.email,
            title="Removed from Company",
            body=(f"You have been removed as an editor from '{company.name}'."),
            channels=["IN_APP", "PUSH"],
            data={
                "companyId": str(company.id),
                "companyName": company.name,
            },
        )

    _async(_send)


# ============================================================
# COMMUNITY NOTIFICATIONS
# ============================================================


def notify_post_liked(post, liked_by):
    """Sent to post author when someone likes their post."""
    if post.author == liked_by:
        return  # Don't notify self-likes

    author = post.author

    def _send():
        send_notification(
            event="POST_LIKED",
            user_id=author.id,
            title="Someone liked your post",
            body=f"{liked_by.get_full_name() or liked_by.username} liked your post.",
            channels=["IN_APP", "PUSH"],
            data={
                "postId": post.id,
                "likedBy": str(liked_by.id),
                "likedByName": liked_by.get_full_name() or liked_by.username,
            },
        )

    _async(_send)


def notify_post_commented(comment):
    """Sent to post author when someone comments on their post."""
    post = comment.post
    if post.author == comment.author:
        return  # Don't notify self-comments

    author = post.author

    def _send():
        send_notification(
            event="POST_COMMENTED",
            user_id=author.id,
            title="New comment on your post",
            body=(
                f"{comment.author.get_full_name() or comment.author.username} "
                "commented on your post."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "postId": post.id,
                "commentId": comment.id,
                "commentedBy": str(comment.author.id),
            },
        )

    _async(_send)


def notify_comment_replied(reply):
    """Sent to comment author when someone replies to their comment."""
    parent_comment = reply.parent
    if not parent_comment:
        return

    if parent_comment.author == reply.author:
        return  # Don't notify self-replies

    comment_author = parent_comment.author

    def _send():
        send_notification(
            event="COMMENT_REPLIED",
            user_id=comment_author.id,
            title="New reply to your comment",
            body=(
                f"{reply.author.get_full_name() or reply.author.username} "
                "replied to your comment."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "postId": reply.post.id,
                "commentId": parent_comment.id,
                "replyId": reply.id,
                "repliedBy": str(reply.author.id),
            },
        )

    _async(_send)


def notify_comment_liked(comment, liked_by):
    """Sent to comment author when someone likes their comment."""
    if comment.author == liked_by:
        return  # Don't notify self-likes

    author = comment.author

    def _send():
        send_notification(
            event="COMMENT_LIKED",
            user_id=author.id,
            title="Someone liked your comment",
            body=(
                f"{liked_by.get_full_name() or liked_by.username} liked your comment."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "commentId": comment.id,
                "postId": comment.post.id,
                "likedBy": str(liked_by.id),
            },
        )

    _async(_send)


# ============================================================
# SUBSCRIPTION NOTIFICATIONS
# ============================================================


def notify_subscription_activated(subscription):
    """Sent to user when their subscription is successfully activated."""
    user = subscription.user

    def _send():
        send_notification(
            event="SUBSCRIPTION_ACTIVATED",
            user_id=user.id,
            user_email=user.email,
            title="Subscription Activated!",
            body=(
                f"Your {subscription.plan.name} subscription is now active "
                f"until {subscription.end_date.strftime('%d %b %Y')}. Enjoy premium access!"
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "planName": subscription.plan.name,
                "endDate": subscription.end_date.isoformat(),
            },
        )

    _async(_send)


def notify_subscription_expiring_soon(subscription):
    """
    Sent to user when their subscription is expiring in 3 days.
    This will be triggered by a Celery Beat scheduled task (Phase 5).
    """
    user = subscription.user

    def _send():
        send_notification(
            event="SUBSCRIPTION_EXPIRING_SOON",
            user_id=user.id,
            user_email=user.email,
            title="Subscription Expiring Soon ⏳",
            body=(
                f"Your {subscription.plan.name} subscription expires on "
                f"{subscription.end_date.strftime('%d %b %Y')}. "
                "Renew now to keep your premium access."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "planName": subscription.plan.name,
                "endDate": subscription.end_date.isoformat(),
            },
        )

    _async(_send)


def notify_subscription_expired(subscription):
    """
    Sent to user when their subscription has expired.
    This will be triggered by a Celery Beat scheduled task (Phase 5).
    """
    user = subscription.user

    def _send():
        send_notification(
            event="SUBSCRIPTION_EXPIRED",
            user_id=user.id,
            user_email=user.email,
            title="Subscription Expired",
            body=(
                f"Your {subscription.plan.name} subscription has expired. "
                "Subscribe again to continue enjoying premium features."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "planName": subscription.plan.name,
            },
        )

    _async(_send)


# ============================================================
# AUTH / ACCOUNT NOTIFICATIONS
# ============================================================


def notify_welcome_user(user):
    """
    Sent to user immediately after successful registration.
    Wire this into RegisterAPIView in users/views.py
    """

    def _send():
        send_notification(
            event="WELCOME_USER",
            user_id=user.id,
            user_email=user.email,
            title="Welcome to the Platform! 🎉",
            body=(
                "Your account has been created successfully. "
                "Explore experts, investors, entrepreneurs and more."
            ),
            channels=["IN_APP", "PUSH"],
            data={"userId": str(user.id)},
        )

    _async(_send)


def notify_password_changed(user):
    """
    Security alert sent when a user changes their password.
    Wire this into PasswordChangeAPIView in users/views.py
    """

    def _send():
        send_notification(
            event="PASSWORD_CHANGED",
            user_id=user.id,
            user_email=user.email,
            title="Password Changed",
            body=(
                "Your password was just changed successfully. "
                "If this wasn't you, contact support immediately."
            ),
            channels=["IN_APP", "PUSH"],
            data={"userId": str(user.id)},
        )

    _async(_send)


def notify_account_banned(user):
    """Sent to user when their account is banned by admin."""

    def _send():
        send_notification(
            event="ACCOUNT_BANNED",
            user_id=user.id,
            user_email=user.email,
            title="Account Suspended",
            body=(
                "Your account has been suspended. "
                "Please contact support for more information."
            ),
            channels=["IN_APP"],
            data={"userId": str(user.id)},
        )

    _async(_send)


# ============================================================
# CHAT NOTIFICATIONS
# ============================================================


def notify_new_message(message, recipient):
    """
    Sent to the recipient when a new chat message arrives.
    Only fires for the OTHER party (not the sender).
    Wire this into chat/consumers.py inside save_message().
    """
    sender = message.sender

    def _send():
        send_notification(
            event="NEW_CHAT_MESSAGE",
            user_id=recipient.id,
            title=f"New message from {sender.get_full_name() or sender.username}",
            body=message.text[:100] if message.text else "Sent an attachment",
            channels=["IN_APP", "PUSH"],
            data={
                "roomId": message.room.id,
                "senderId": str(sender.id),
                "senderName": sender.get_full_name() or sender.username,
            },
        )

    _async(_send)


def notify_chat_room_created(room):
    """
    Sent to both parties when a chat room is created (after booking confirmation).
    """
    user = room.user
    advisor = room.advisor

    def _send():
        # Notify user
        send_notification(
            event="CHAT_ROOM_CREATED",
            user_id=user.id,
            title="Chat Room Open",
            body=(
                f"Your chat room with {advisor.get_full_name() or advisor.username} "
                "is now open. Start the conversation!"
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "roomId": room.id,
                "advisorName": advisor.get_full_name() or advisor.username,
            },
        )

        # Notify advisor
        send_notification(
            event="CHAT_ROOM_CREATED",
            user_id=advisor.id,
            title="Chat Room Open",
            body=(
                f"Your chat room with {user.get_full_name() or user.username} "
                "is now open."
            ),
            channels=["IN_APP", "PUSH"],
            data={
                "roomId": room.id,
                "userName": user.get_full_name() or user.username,
            },
        )

    _async(_send)
