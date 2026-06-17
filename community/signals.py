from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PostMedia


@receiver(post_delete, sender=PostMedia)
def delete_postmedia_file_on_delete(sender, instance, **kwargs):
    """Delete the physical file when a PostMedia row is removed —
    including cascade deletes when the parent Post is deleted, and
    bulk QuerySet deletes from the post-update flow."""
    if instance.file:
        instance.file.delete(save=False)