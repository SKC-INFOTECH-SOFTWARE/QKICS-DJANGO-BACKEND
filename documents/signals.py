from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db.models.signals import pre_save
from .models import Document


@receiver(post_delete, sender=Document)
def delete_document_file_on_delete(sender, instance, **kwargs):
    """Delete the physical file when a Document row is removed."""
    if instance.file:
        instance.file.delete(save=False)


@receiver(pre_save, sender=Document)
def delete_old_document_file_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return  # new object, nothing to replace
    try:
        old_file = Document.objects.get(pk=instance.pk).file
    except Document.DoesNotExist:
        return
    new_file = instance.file
    if old_file and old_file != new_file:
        old_file.delete(save=False)
