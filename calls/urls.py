from django.urls import path
from .views import (
    MyCallRoomsView, MyCallNotesView,
    CallRoomDetailView, EndCallView,
    CallMessageListView, CallFileUploadView,
    CallNoteView,
    LiveKitWebhookView,
    AdminCallRecordingListView, AdminCallRecordingSignedUrlView,
)

urlpatterns = [
    # ── User-facing ──────────────────────────────────────
    path("my/",       MyCallRoomsView.as_view(), name="my-call-rooms"),
    path("notes/my/", MyCallNotesView.as_view(), name="my-call-notes"),

    path("<uuid:room_id>/",           CallRoomDetailView.as_view(),  name="call-room-detail"),
    path("<uuid:room_id>/end/",       EndCallView.as_view(),         name="call-room-end"),
    path("<uuid:room_id>/messages/",  CallMessageListView.as_view(), name="call-messages"),
    path("<uuid:room_id>/upload/",    CallFileUploadView.as_view(),  name="call-file-upload"),
    path("<uuid:room_id>/notes/",     CallNoteView.as_view(),        name="call-notes"),

    # ── LiveKit webhook ───────────────────────────────────
    path("livekit/webhook/", LiveKitWebhookView.as_view(), name="livekit-webhook"),

    # ── Admin ─────────────────────────────────────────────
    path("admin/recordings/",
         AdminCallRecordingListView.as_view(), name="admin-call-recordings"),
    path("admin/recordings/<uuid:recording_id>/signed-url/",
         AdminCallRecordingSignedUrlView.as_view(), name="admin-recording-signed-url"),
]
