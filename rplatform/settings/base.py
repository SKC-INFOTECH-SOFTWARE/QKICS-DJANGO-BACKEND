from .base import *
from decouple import config

# ==================================================
# CORE
# ==================================================
DEBUG = False

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS", default="", cast=str
).split(",")

# ==================================================
# SECURITY
# ==================================================
SECURE_SSL_REDIRECT = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# ==================================================
# CORS / CSRF
# ==================================================
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS", default="", cast=str
).split(",")

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS", default="", cast=str
).split(",")

# ==================================================
# STATIC FILES
# ==================================================
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

# ==================================================
# DATABASE (OPTIONAL SSL – ENABLE FOR CLOUD DB)
# ==================================================
DATABASES["default"]["OPTIONS"].update(
    {
        "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
    }
)

# ==================================================
# EMAIL (ONLY IF USED)
# ==================================================
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# ==================================================
# LOGGING (PRODUCTION SAFE)
# ==================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
# ==================================================
# REDIS CACHE
# ==================================================
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{config('REDIS_HOST', default='127.0.0.1')}:{config('REDIS_PORT', default=6379)}/0",
    }
}
