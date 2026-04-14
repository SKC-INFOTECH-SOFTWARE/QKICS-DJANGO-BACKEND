import logging
import os
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CallsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calls"

    def ready(self):
        import sys
        # Skip during management commands that don't need the scheduler
        skip_commands = {"migrate", "makemigrations", "test", "collectstatic", "shell"}
        if any(cmd in sys.argv for cmd in skip_commands):
            return

        try:
            from calls.services.auto_cut import get_scheduler
            scheduler = get_scheduler()
            if scheduler.running:
                logger.info("APScheduler running — auto-cut jobs active.")
        except Exception as e:
            logger.error("APScheduler init failed: %s", e)
