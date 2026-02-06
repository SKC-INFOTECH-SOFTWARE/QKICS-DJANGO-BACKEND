from .base import *

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "192.168.0.123"]

# CORS (React + Flutter dev)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

# CSRF (HTTP dev)
CSRF_COOKIE_SECURE = False
CSRF_COOKIE_SAMESITE = "Lax"

# Allow common local development IPs
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^http://10\.0\.2\.2:\d+$",        # Android emulator
    r"^http://192\.168\.\d+\.\d+:\d+$", # Local network dev
]
