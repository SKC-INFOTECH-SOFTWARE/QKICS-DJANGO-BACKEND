import threading
from .client import send_notification


def _async(fn, *args, **kwargs):
    """Run notification sending in a background thread so it never blocks the request."""
    t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
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
    """
    user = booking.user
    expert = booking.expert

    def _send():
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
            channels=["IN_APP"],
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
            body=f"{comment.author.get_full_name() or comment.author.username} commented on your post.",
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
            body=f"{reply.author.get_full_name() or reply.author.username} replied to your comment.",
            channels=["IN_APP", "PUSH"],
            data={
                "postId": reply.post.id,
                "commentId": parent_comment.id,
                "replyId": reply.id,
                "repliedBy": str(reply.author.id),
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


# ============================================================
# CHAT NOTIFICATIONS
# ============================================================


def notify_new_message(message, recipient):
    """
    Sent to the recipient when a new chat message arrives.
    Only fires for the OTHER party (not the sender).
    This is a lightweight IN_APP + PUSH only notification.
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
