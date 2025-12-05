from .base import *
from decouple import config

DEBUG = False

# Allowed backend domain
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=str).split(",")

# Only allow your production web apps
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=str).split(",")
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=str).split(",")

CORS_ALLOW_CREDENTIALS = True

# Security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
