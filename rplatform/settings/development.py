from .base import *

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Allow everything in development (React + Flutter)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "None"

# Allow common local development IPs
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^http://10\.0\.2\.2:\d+$",       # Android emulator
    r"^http://192\.168\.\d+\.\d+:\d+$", # Local network dev
]
