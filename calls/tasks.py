"""
calls/tasks.py

7-day recording cleanup — deletes from Cloudinary.

Cron (VPS mein add karo):
  0 2 * * * cd /opt/qkics && docker compose -f docker-compose.prod.yml exec -T django python manage.py cleanup_recordings >> /var/log/qkics_cleanup.log 2>&1
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def cleanup_expired_recordings():
    from calls.models import CallRecording

    now     = timezone.now()
    expired = CallRecording.objects.filter(
        delete_after__lte=now,
        status__in=[
            CallRecording.STATUS_READY,
            CallRecording.STATUS_FAILED,
            CallRecording.STATUS_UPLOADING,
        ],
    )

    count = 0
    for rec in expired:
        try:
            # Delete from Cloudinary
            if rec.cloudinary_public_id:
                from calls.services.livekit_service import delete_cloudinary_recording
                delete_cloudinary_recording(public_id=rec.cloudinary_public_id)

            # Delete local file if still exists (edge case — upload failed)
            if rec.local_file_path:
                import os
                if os.path.exists(rec.local_file_path):
                    os.remove(rec.local_file_path)
                    logger.info("Local file deleted: %s", rec.local_file_path)

            # Mark deleted in DB
            rec.status                = CallRecording.STATUS_DELETED
            rec.deleted_at            = now
            rec.cloudinary_public_id  = ""
            rec.cloudinary_secure_url = ""
            rec.local_file_path       = ""
            rec.save(update_fields=[
                "status", "deleted_at",
                "cloudinary_public_id", "cloudinary_secure_url",
                "local_file_path",
            ])

            count += 1
            logger.info("Recording %s deleted from Cloudinary", rec.id)

        except Exception as e:
            logger.error("Failed to delete recording %s: %s", rec.id, e)

    logger.info("Cleanup done: %d recordings deleted.", count)
    return count
