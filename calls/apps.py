import logging
import os
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class CallsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "calls"

    def ready(self):
        is_dev_main = os.environ.get("RUN_MAIN") == "true"
        is_prod     = not os.environ.get("DJANGO_SETTINGS_MODULE", "").endswith("development")

        if is_dev_main or is_prod:
            try:
                from calls.services.auto_cut import get_scheduler
                scheduler = get_scheduler()
                if scheduler.running:
                    logger.info("APScheduler running — auto-cut jobs active.")
            except Exception as e:
                logger.error("APScheduler init failed: %s", e)
