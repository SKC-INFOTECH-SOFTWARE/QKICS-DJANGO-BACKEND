from django.core.management.base import BaseCommand
from calls.tasks import cleanup_expired_recordings


class Command(BaseCommand):
    help = "Delete call recordings from the local /recordings volume that are past their retention period (15 days)"

    def handle(self, *args, **options):
        self.stdout.write("Starting local recording cleanup...")
        count = cleanup_expired_recordings()
        self.stdout.write(self.style.SUCCESS(f"Done. {count} recordings deleted from local storage."))
