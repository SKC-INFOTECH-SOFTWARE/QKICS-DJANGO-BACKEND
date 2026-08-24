from django.db import models


class SystemLog(models.Model):
    """
    Application-wide system log, surfaced to superadmins in the admin panel.

    Rows are written automatically by `adminpanel.logging_handler.DatabaseLogHandler`
    (attached to the root logger at WARNING+ level), so every `logger.warning(...)`
    / `logger.error(...)` / `logger.exception(...)` anywhere in the codebase lands
    here without per-call-site instrumentation. Code can also call
    `log_system_event(...)` for an explicit audit entry.
    """

    LEVEL_DEBUG    = "DEBUG"
    LEVEL_INFO     = "INFO"
    LEVEL_WARNING  = "WARNING"
    LEVEL_ERROR    = "ERROR"
    LEVEL_CRITICAL = "CRITICAL"

    LEVEL_CHOICES = (
        (LEVEL_DEBUG,    "Debug"),
        (LEVEL_INFO,     "Info"),
        (LEVEL_WARNING,  "Warning"),
        (LEVEL_ERROR,    "Error"),
        (LEVEL_CRITICAL, "Critical"),
    )

    # Coarse category derived from the logger name (payments / bookings / calls …)
    # so admins can filter by area without parsing the logger path.
    CATEGORY_CHOICES = (
        ("AUTH",       "Auth"),
        ("PAYMENT",    "Payment"),
        ("BOOKING",    "Booking"),
        ("CALL",       "Call / Recording"),
        ("CHAT",       "Chat"),
        ("COMMUNITY",  "Community"),
        ("NOTIFICATION", "Notification"),
        ("ADMIN",      "Admin"),
        ("SYSTEM",     "System"),
    )

    id          = models.BigAutoField(primary_key=True)
    level       = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_INFO, db_index=True)
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="SYSTEM", db_index=True)
    logger_name = models.CharField(max_length=200, blank=True, default="")
    message     = models.TextField(blank=True, default="")
    # Optional structured extras / traceback text.
    detail      = models.TextField(blank=True, default="")
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["level", "created_at"]),
            models.Index(fields=["category", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.logger_name}: {self.message[:60]}"


def category_for_logger(logger_name: str) -> str:
    """Map a dotted logger name to a coarse SystemLog category."""
    name = (logger_name or "").lower()
    if name.startswith(("users", "rest_framework_simplejwt", "django.security")):
        return "AUTH"
    if name.startswith("payments") or "payu" in name:
        return "PAYMENT"
    if name.startswith("bookings"):
        return "BOOKING"
    if name.startswith("calls"):
        return "CALL"
    if name.startswith("chat"):
        return "CHAT"
    if name.startswith("community"):
        return "COMMUNITY"
    if name.startswith("notifications"):
        return "NOTIFICATION"
    if name.startswith("adminpanel"):
        return "ADMIN"
    return "SYSTEM"


def log_system_event(*, level="INFO", message="", logger_name="adminpanel", detail="", category=None):
    """
    Write an explicit SystemLog row. Never raises — logging must not break callers.
    """
    try:
        SystemLog.objects.create(
            level=level[:10],
            category=category or category_for_logger(logger_name),
            logger_name=(logger_name or "")[:200],
            message=(message or "")[:8000],
            detail=(detail or "")[:8000],
        )
    except Exception:
        pass
