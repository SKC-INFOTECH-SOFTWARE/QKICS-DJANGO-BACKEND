from django.urls import path

from meetings.views import (
    AdminMeetingAttendanceView,
    AdminMeetingDetailView,
    AdminMeetingEndView,
    AdminMeetingInviteDeleteView,
    AdminMeetingInvitesView,
    AdminMeetingListCreateView,
    AdminMeetingRegenerateLinkView,
    MyMeetingsView,
    PublicMeetingDetailView,
    PublicMeetingJoinView,
)

urlpatterns = [
    # ── Admin ─────────────────────────────────────────────
    path("admin/", AdminMeetingListCreateView.as_view(), name="admin-meetings"),
    path(
        "admin/<uuid:meeting_id>/",
        AdminMeetingDetailView.as_view(),
        name="admin-meeting-detail",
    ),
    path(
        "admin/<uuid:meeting_id>/end/",
        AdminMeetingEndView.as_view(),
        name="admin-meeting-end",
    ),
    path(
        "admin/<uuid:meeting_id>/regenerate-link/",
        AdminMeetingRegenerateLinkView.as_view(),
        name="admin-meeting-regenerate-link",
    ),
    path(
        "admin/<uuid:meeting_id>/invites/",
        AdminMeetingInvitesView.as_view(),
        name="admin-meeting-invites",
    ),
    path(
        "admin/<uuid:meeting_id>/invites/<int:invite_id>/",
        AdminMeetingInviteDeleteView.as_view(),
        name="admin-meeting-invite-delete",
    ),
    path(
        "admin/<uuid:meeting_id>/attendance/",
        AdminMeetingAttendanceView.as_view(),
        name="admin-meeting-attendance",
    ),

    # ── Signed-in users ───────────────────────────────────
    path("my/", MyMeetingsView.as_view(), name="my-meetings"),

    # ── Public link (token) — keep last so "admin"/"my" win ──
    path("<str:token>/", PublicMeetingDetailView.as_view(), name="meeting-detail"),
    path("<str:token>/join/", PublicMeetingJoinView.as_view(), name="meeting-join"),
]
