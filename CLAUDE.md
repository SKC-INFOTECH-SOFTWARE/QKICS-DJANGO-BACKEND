# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`rplatform` (project codename **qkics**) is a Django 5.2 + DRF backend for a platform that
connects **experts, entrepreneurs, and investors** with consultation bookings, scheduled
video calls (LiveKit), real-time chat, a community feed, payments, subscriptions, ads, and
companies. It is an ASGI app (Channels/Daphne) backed by **MySQL** and **Redis**.

## Commands

Settings are selected by the `PROJECT_ENV` env var (`development` by default, `prod` for
production) — see `manage.py` and `rplatform/asgi.py`. There is no `settings.py`; it's the
`rplatform/settings/` package (`base.py` → `development.py` / `production.py`).

```bash
# Local (venv) — DJANGO_SETTINGS_MODULE resolves via PROJECT_ENV
python manage.py migrate
python manage.py runserver            # dev, sync; use Daphne for WebSockets
daphne -b 0.0.0.0 -p 8000 rplatform.asgi:application   # ASGI (chat + calls)
python manage.py makemigrations <app>
python manage.py createsuperuser

# Tests (Django test runner; each app has a tests.py, mostly stubs)
python manage.py test                 # all
python manage.py test calls           # one app
python manage.py test calls.tests.SomeTestCase.test_method   # single test

# Management commands
python manage.py cleanup_recordings   # delete Cloudinary recordings past delete_after

# Docker (dev) — Django on :8000, Redis on :6380
docker compose -f docker-compose.dev.yml up
```

Redis runs on **port 6380** (non-default) in both dev compose and settings.

Lint in CI is non-blocking: `flake8 . --select=E9,F63,F7,F82` (syntax/undefined-name only).

## Architecture

### Domain apps
URLs are namespaced under `/api/v1/<app>/` in `rplatform/urls.py`.

- `users` — custom `AUTH_USER_MODEL = users.User` (`AbstractUser` + `uuid`, `user_type`,
  `status`). `user_type` ∈ {superadmin, admin, expert, entrepreneur, investor, normal} drives
  role-based access throughout. The model's `save()` auto-compresses uploaded profile pictures
  to ≤200KB JPEG and cleans up old files.
- `experts`, `entrepreneurs`, `investors` — role-specific profile apps keyed off `User`.
- `bookings` — consultation scheduling; a confirmed booking provisions a LiveKit `CallRoom`.
- `calls` — video call rooms + recordings (LiveKit, see below).
- `chat` — WebSocket messaging.
- `community` — posts/comments/replies feed.
- `companies`, `ads`, `documents`, `payments`, `subscriptions` — supporting domains.
- `adminpanel` — admin-facing list/management APIs (DRF + `django_filters`).
- `notifications` — thin client that POSTs to an **external** notification microservice
  (`NOTIFICATION_SERVICE_URL`), see `notifications/services/`.

### Per-app conventions
Each app follows DRF layout: `models.py`, `serializers.py`, `views.py`, `urls.py`,
`permissions.py`, and (where relevant) a `services/` package holding business logic and
external integrations. Put non-trivial logic in `services/`, not in views. List endpoints use
`DjangoFilterBackend` + DRF `SearchFilter` for search/filter (recent feature work).

### Auth
JWT via `rest_framework_simplejwt` (access 1d, refresh 30d, rotation + blacklist enabled).
DRF defaults to `IsAuthenticated` globally. WebSockets authenticate via a `?token=` query
param handled by `chat.middleware.JWTAuthMiddleware` (wired in `rplatform/asgi.py`).

### Real-time (Channels)
`rplatform/asgi.py` is the entrypoint: HTTP → Django, WebSocket → `JWTAuthMiddleware` →
`URLRouter(chat_ws + calls_ws)`. Routes live in each app's `routing.py`:
- chat: `ws/chat/<room_id>/`
- calls: `ws/calls/<room_id>/` (in-call text chat)

Channel layer is `channels_redis` (Redis on 6380).

### Video calls & recordings (LiveKit + Cloudinary)
`calls/services/livekit_service.py` is the integration hub. Flow:
1. Booking confirmed → create LiveKit room; recording starts when first participant joins
   (driven by LiveKit **webhooks**, not the booking flow).
2. LiveKit Egress writes MP4 to local `/recordings/<room_id>.mp4`.
3. `egress_ended` webhook → `upload_recording_to_cloudinary()` (runs in a background thread)
   uploads as a **private** Cloudinary video, then deletes the local file.
4. Admins download via short-lived signed URLs (`generate_cloudinary_signed_url`).
5. After the retention window, `cleanup_recordings` management command / `calls/tasks.py`
   deletes from Cloudinary.

Webhook verification, room lifecycle, and `CallRoom`/`CallRecording` status transitions all
live in `handle_livekit_webhook()`. Note `room_finished` does **not** end a room while its
scheduled slot is still active (participants may rejoin; LiveKit auto-creates rooms).

### Scheduling
`calls/apps.py` `ready()` starts an **APScheduler** instance (`calls/services/auto_cut.py`)
for auto-cutting calls, skipping startup during `migrate`/`makemigrations`/`test`/
`collectstatic`/`shell`. The 7-day recording cleanup runs via a **system cron** that the
deploy workflow installs (calls `cleanup_recordings`), not via APScheduler.

## Environment & deployment

Config is read with `python-decouple` from `.env` (committed examples: `.env`, `.env.dev`).
Required keys include `SECRET_KEY`, `DB_*` (MySQL), `REDIS_*`, `LIVEKIT_*`, `CLOUDINARY_*`,
`TURN_*`, and (prod) `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `EMAIL_*`.

Production runs via `entrypoint.sh` (gunicorn + `uvicorn.workers.UvicornWorker` on :9000,
behind Nginx for SSL). `docker-compose.prod.yml` plus separate LiveKit compose
(`docker-compose.dev.livekit.yml`, `livekit/*.yaml`). CI (`.github/workflows/deploy.yml`)
runs lint → builds/pushes the Docker image to Docker Hub → SSH-deploys to the VPS on push to
`main`/`production`.



Production uses **Cloudflare** for SSL, caching, and WAF. The VPS runs Ubuntu 22.04 LTS with
Docker 24.0.5, Docker Compose 2.20.2, and Nginx 1.22.1. The VPS has a **static IP** and a **domain** (e.g., `example.com`) with a **wildcard SSL cert** for `*.example.com` (used for subdomains like `api.example.com`, `livekit.example.com`, etc.). The VPS is configured to run the Docker containers for the backend, LiveKit, and Nginx reverse proxy. The VPS also has a **cron job** that runs the `cleanup_recordings` management command every 7 days to delete old recordings from Cloudinary.

