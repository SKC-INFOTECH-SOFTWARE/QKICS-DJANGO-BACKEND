from django.core.management.base import BaseCommand
from calls.tasks import cleanup_expired_recordings


class Command(BaseCommand):
    help = "Delete call recordings from Cloudinary that are past their 7-day retention period"

    def handle(self, *args, **options):
        self.stdout.write("Starting Cloudinary recording cleanup...")
        count = cleanup_expired_recordings()
        self.stdout.write(self.style.SUCCESS(f"Done. {count} recordings deleted from Cloudinary."))
