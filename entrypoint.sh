#!/bin/sh

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-rplatform.settings.production}

echo "Using settings: $DJANGO_SETTINGS_MODULE"

python manage.py migrate --noinput
python manage.py collectstatic --noinput

gunicorn rplatform.asgi:application \
  -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:9000 \
  --workers 3 \
  --timeout 120