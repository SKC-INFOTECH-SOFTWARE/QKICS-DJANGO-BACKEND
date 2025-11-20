import os
import sys
from decouple import config


def main():
    """Run administrative tasks."""

    # Read environment mode from .env or .env.prod
    env = config("PROJECT_ENV", default="development").lower()

    # Pick settings based on environment
    if env == "prod":
        settings_module = "rplatform.settings.production"
    else:
        settings_module = "rplatform.settings.development"

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Make sure it's installed and "
            "your virtual environment is activated."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
