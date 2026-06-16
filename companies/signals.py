from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CompanyPostMedia


@receiver(post_delete, sender=CompanyPostMedia)
def delete_media_file_on_delete(sender, instance, **kwargs):
    """Delete the physical file when a CompanyPostMedia row is deleted
    (including cascade deletes when the parent post is removed)."""
    if instance.file:
        instance.file.delete(save=False)
