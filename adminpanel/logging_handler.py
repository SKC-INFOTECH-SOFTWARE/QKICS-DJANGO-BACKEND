"""
adminpanel/logging_handler.py

A logging.Handler that mirrors application log records into the SystemLog table so
superadmins can browse them in the admin panel. Attached to the root logger at
WARNING+ level (see settings LOGGING), so warnings/errors/exceptions from anywhere
in the codebase are captured with no per-call-site changes.

Safety rules (a log handler must NEVER take down the app):
  - swallow every exception (DB down, table missing during migrate, etc.)
  - skip the DB loggers so an ORM write can't recurse into itself
  - stay lightweight: one INSERT per captured record
"""
import logging


class DatabaseLogHandler(logging.Handler):
    # Logger name prefixes we must not persist — writing a SystemLog row itself
    # goes through the DB, and django.db.* would recurse / flood.
    _SKIP_PREFIXES = ("django.db", "django.request.db")

    def emit(self, record):
        name = record.name or ""
        if name.startswith(self._SKIP_PREFIXES):
            return

        try:
            # Imported lazily so app loading / migrations don't trip on a missing
            # table or an unready app registry.
            from adminpanel.models import SystemLog, category_for_logger

            message = record.getMessage()
            detail = ""
            if record.exc_info:
                try:
                    detail = self.formatException(record.exc_info)
                except Exception:
                    detail = ""

            SystemLog.objects.create(
                level=record.levelname[:10],
                category=category_for_logger(name),
                logger_name=name[:200],
                message=message[:8000],
                detail=detail[:8000],
            )
        except Exception:
            # Last resort: never propagate a logging failure to the caller.
            return
