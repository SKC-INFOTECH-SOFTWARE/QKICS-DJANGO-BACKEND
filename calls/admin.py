from django.contrib import admin
from django.utils.html import format_html
from .models import CallRoom, CallParticipant, CallRecording, CallMessage, CallNote


class CallParticipantInline(admin.TabularInline):
    model           = CallParticipant
    extra           = 0
    can_delete      = False
    readonly_fields = ["user", "joined_at", "left_at", "dur"]

    def dur(self, obj):
        d = obj.duration_seconds
        return f"{d // 60}m {d % 60}s" if d else "In call"
    dur.short_description = "Duration"


class CallRecordingInline(admin.TabularInline):
    model           = CallRecording
    extra           = 0
    can_delete      = False
    readonly_fields = ["id", "status", "cloudinary_public_id", "size_mb", "started_at", "delete_after"]

    def size_mb(self, obj):
        return f"{obj.file_size_bytes / 1024 / 1024:.1f} MB" if obj.file_size_bytes else "—"


@admin.register(CallRoom)
class CallRoomAdmin(admin.ModelAdmin):
    list_display    = ["id", "user", "advisor", "status", "scheduled_start", "dur", "rec_status", "created_at"]
    list_filter     = ["status", "created_at"]
    search_fields   = ["user__username", "advisor__username", "sfu_room_name"]
    readonly_fields = ["id", "sfu_room_name", "started_at", "ended_at", "created_at", "updated_at"]
    inlines         = [CallParticipantInline, CallRecordingInline]

    def dur(self, obj):
        d = obj.duration_seconds
        return f"{d // 60}m {d % 60}s" if d else "—"
    dur.short_description = "Duration"

    def rec_status(self, obj):
        rec = obj.recordings.exclude(status=CallRecording.STATUS_DELETED).first()
        if not rec:
            return "—"
        colors = {"READY": "green", "RECORDING": "orange", "UPLOADING": "blue", "FAILED": "red"}
        color  = colors.get(rec.status, "gray")
        return format_html('<b style="color:{}">{}</b>', color, rec.status)
    rec_status.short_description = "Recording"


@admin.register(CallRecording)
class CallRecordingAdmin(admin.ModelAdmin):
    list_display    = ["id", "participants", "status", "size_mb", "started_at", "delete_after"]
    list_filter     = ["status", "started_at"]
    readonly_fields = ["id", "room", "egress_id", "cloudinary_public_id", "cloudinary_secure_url",
                       "local_file_path", "file_size_bytes", "duration_seconds",
                       "started_at", "ended_at", "delete_after", "deleted_at"]

    def participants(self, obj):
        return f"{obj.room.user.username} ↔ {obj.room.advisor.username}"

    def size_mb(self, obj):
        return f"{obj.file_size_bytes / 1024 / 1024:.1f} MB" if obj.file_size_bytes else "—"

    def has_delete_permission(self, request, obj=None):
        return False  # Use cleanup_recordings command


@admin.register(CallNote)
class CallNoteAdmin(admin.ModelAdmin):
    list_display    = ["id", "user", "room", "preview", "updated_at"]
    search_fields   = ["user__username", "content"]
    readonly_fields = ["room", "user", "created_at", "updated_at"]

    def preview(self, obj):
        return obj.content[:60] or "—"


@admin.register(CallMessage)
class CallMessageAdmin(admin.ModelAdmin):
    list_display    = ["id", "sender", "room", "preview", "has_file", "created_at"]
    search_fields   = ["sender__username", "text"]
    readonly_fields = ["room", "sender", "text", "file", "file_name", "file_size_bytes", "created_at"]

    def preview(self, obj):
        return obj.text[:50] or "—"

    def has_file(self, obj):
        return bool(obj.file)
    has_file.boolean = True
