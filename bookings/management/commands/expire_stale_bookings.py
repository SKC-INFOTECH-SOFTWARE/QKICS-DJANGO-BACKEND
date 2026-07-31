"""
Expire abandoned-checkout bookings so their slots free up.

Runs automatically every few minutes via APScheduler (see calls/apps.py), but is
also exposed as a command for manual runs and as a cron fallback:

    python manage.py expire_stale_bookings
"""

from django.core.management.base import BaseCommand

from bookings.services.expire_stale import expire_stale_bookings


class Command(BaseCommand):
    help = "Expire stale PENDING/AWAITING_PAYMENT bookings and release their slots."

    def handle(self, *args, **options):
        count = expire_stale_bookings()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} stale booking(s)."))
