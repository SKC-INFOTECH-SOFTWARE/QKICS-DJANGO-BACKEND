# Admin Meeting Links — API & Mobile Guide

An admin creates a meeting in the admin panel, gets a **short shareable link**, and
sends it to anyone. People open the link and join — **a Qkics account is optional**:
if guests are allowed they just type their name, and that name is what everyone in
the call sees.

Every meeting is **recorded automatically**, and the recording is **deleted from the
server after 3 days**.

> Backend ships this. Nothing here needs a server change — build the pre-join
> screen and reuse the existing group-call screen.

---

## 1. What a meeting actually is

A `Meeting` is an *entry door* to a regular `calls.CallRoom`. Instead of reaching
the room through a booking or an expert slot, you reach it with `invite_token`.
Everything downstream is the existing machinery, unchanged:

| Feature | Where it comes from |
|---|---|
| Video/audio, gallery grid for N people | LiveKit + the existing batch (group) call UI |
| In-call text chat | `ws/calls/<room_id>/` |
| Host mute / mute-all / remove participant | `POST /api/v1/calls/<room_id>/mute|mute-all|remove/` |
| Raise hand, active speaker | LiveKit data channel (already implemented) |
| Recording | LiveKit egress, started by webhook on first join |
| Attendance | `calls.CallParticipant`, written by LiveKit webhooks |

So: **treat a meeting room as a batch room.** `GET /api/v1/calls/<room_id>/` now
returns `is_meeting: true` and `meeting_title`; use the group layout when either
`is_batch` or `is_meeting` is true.

---

## 2. The link

```
https://<frontend>/m/<invite_token>
```

`invite_token` is **12 characters** from `abcdefghijkmnpqrstuvwxyz23456789` —
no `0/O`, no `1/l/I`, so it survives being read aloud or retyped.

```
https://qkics.com/m/endwcue4fr6r
```

- ~60 bits of entropy — not enumerable.
- Expires **12 hours** after the scheduled end (or after creation, for an instant
  meeting).
- The admin can revoke it at any time (`regenerate-link` below): the old link
  immediately returns 404.
- `/meet/<token>` works too, as an alias.

Deep link for the app: handle `qkics://m/<token>` and the universal link
`https://<frontend>/m/<token>` → open the pre-join screen.

---

## 3. Pre-join screen

### `GET /api/v1/meetings/<token>/`
Auth **optional**. Call it as soon as the screen opens.

```json
{
  "id": "36e1df1e-…",
  "title": "Investor briefing",
  "description": "Q3 numbers",
  "host_name": "Ravi Menon",
  "scheduled_start": null,
  "scheduled_end": null,
  "status": "SCHEDULED",
  "can_join_now": true,
  "join_opens_at": null,
  "requires_invite": false,
  "is_recorded": true,
  "allows_guests": true,
  "requires_login": true,
  "can_join": true,
  "reason": "",
  "is_host": false,
  "needs_name": true
}
```

Field meanings that drive the UI:

| Field | Use |
|---|---|
| `can_join` | Enable/disable the Join button |
| `reason` | Why they can't join (show as-is) |
| `needs_name` | **Show the name field** — a guest can get in with just a name |
| `allows_guests` | Whether this meeting accepts people without an account |
| `requires_login` | Show a **Sign in** button — signing in *would* let them in |
| `is_host` | They created the meeting |
| `is_recorded` | Always true — show the recording notice |

Decision table for a **signed-out** visitor:

```
needs_name = true                → name field + "Join meeting"
requires_login = true            → "Sign in to join" button
neither, and can_join = false     → show `reason` (too early / ended / cancelled)
```

An **INVITED_ONLY** meeting opened by a signed-out visitor returns only
`{"requires_login": true, "requires_invite": true, "detail": "Sign in to see this meeting."}`
— no title, no time. Show a generic "Sign in to continue" screen.

Errors: `404 {"detail": "This meeting link is invalid."}` for a bad or revoked token.

---

## 4. Joining

### `POST /api/v1/meetings/<token>/join/`
Auth **optional**.

**Signed-in user** — send an empty body with the JWT:
```json
{}
```

**Guest (no account)** — send the name, no auth header:
```json
{ "display_name": "Asha Verma" }
```

Response (both cases):
```json
{
  "room_id": "9b018ae0-…",
  "meeting_id": "36e1df1e-…",
  "title": "Investor briefing",
  "livekit_token": "eyJhbGciOi…",
  "livekit_url": "wss://livekit.example.com",
  "identity": "guest_4c415f27-…",
  "display_name": "Asha Verma",
  "is_host": false,
  "is_guest": true,
  "guest_token": "eyJn…:1t…:Xy…",
  "is_recorded": true,
  "scheduled_end": null
}
```

Then connect to LiveKit with `livekit_url` + `livekit_token` and render the group
call screen. **Do not** call `GET /api/v1/calls/<room_id>/` as a guest — it needs a
JWT. Everything you need is in this response.

- `identity` is the LiveKit participant identity: the user id for accounts,
  `guest_<uuid>` for guests. Host mute/remove address people by this string, so
  guests are controllable exactly like signed-in participants.
- `display_name` is what LiveKit shows — the name the guest typed (whitespace
  collapsed, control characters stripped, 60 chars max).
- `guest_token` is **only** for the chat socket (below). It is not a JWT and opens
  nothing else. Valid 6 hours, scoped to this one meeting.

Validation / refusals:

| Response | Meaning |
|---|---|
| `400 {"display_name": ["Please enter your name (at least 2 characters)."]}` | Empty or 1-char name |
| `403 {"detail": "…", "requires_login": true}` | Guests not allowed here — offer sign-in |
| `403 {"detail": "…", "requires_login": false}` | Too early / ended / cancelled / waiting for host — show the message, do **not** offer sign-in |
| `403 {"detail": "You are not on the invite list for this meeting."}` | Signed in but not invited |
| `404` | Invalid or revoked link |
| `503` | LiveKit unreachable — offer retry |

Join window: participants may enter **10 minutes** before `scheduled_start`. The
host can enter any time. An instant meeting (no `scheduled_start`) is open at once.

---

## 5. In-call chat for guests

Same socket as always, different query parameter:

```
signed-in : ws/calls/<room_id>/?token=<jwt>
guest     : ws/calls/<room_id>/?guest=<guest_token>
```

Message frames now carry guest-safe fields:

```json
{
  "type": "call_message",
  "message_id": 42,
  "text": "hi from guest",
  "sender_id": "guest_1fd5b397-…",
  "sender_username": "Asha Verma",
  "timestamp": "2026-09-28T…"
}
```

`sender_id` equals the LiveKit `identity`, so you can match a chat message to the
video tile for both kinds of participant. `GET /api/v1/calls/<room_id>/messages/`
(signed-in only) now also returns `sender_id`, `sender_name` and `is_guest`
alongside the old `sender` object — `sender` is `null` for guest messages.

Notes on guest limits (by design):
- Guests get **no chat history** on join (history needs a signed-in session); they
  see messages sent from the moment they connect.
- Private call notes are a signed-in feature.
- Host chat-block works on guests: the host sends
  `{"type": "block_user", "user_id": "guest_<uuid>", "blocked": true}`.

---

## 6. Admin endpoints

All require a JWT whose `user_type` is `admin` or `superadmin`.

```
GET    /api/v1/meetings/admin/                              list (paginated)
         ?status=SCHEDULED|LIVE|ENDED|CANCELLED &access_mode= &host=
         &search=<title/description/host> &ordering=-created_at|scheduled_start
POST   /api/v1/meetings/admin/                              create
GET    /api/v1/meetings/admin/<id>/                         detail
PATCH  /api/v1/meetings/admin/<id>/                         edit (not once ENDED/CANCELLED)
DELETE /api/v1/meetings/admin/<id>/                         cancel (record kept)
POST   /api/v1/meetings/admin/<id>/end/                     end now, stop recording
POST   /api/v1/meetings/admin/<id>/regenerate-link/         revoke old link
GET    /api/v1/meetings/admin/<id>/invites/                 list invitees
POST   /api/v1/meetings/admin/<id>/invites/                 invite
DELETE /api/v1/meetings/admin/<id>/invites/<invite_id>/     remove an invitee
GET    /api/v1/meetings/admin/<id>/attendance/              who joined + recordings
```

### Create
```json
{
  "title": "Investor briefing",
  "description": "Q3 numbers",
  "access_mode": "ANYONE_WITH_LINK",
  "allow_guests": true,
  "max_participants": 20,
  "require_host": false,
  "scheduled_start": "2026-10-02T10:00:00Z",
  "scheduled_end":   "2026-10-02T11:00:00Z"
}
```
Omit both datetimes for an **instant** meeting. Sending one without the other is a
400 — a scheduled meeting needs both. `max_participants` is 2–100.

`access_mode`:
- `ANYONE_WITH_LINK` — anyone holding the link. Combine with `allow_guests: true`
  to let people in without an account.
- `INVITED_ONLY` — only users on the invite list; always requires a login, and
  `allow_guests` is ignored.

`require_host: true` — nobody enters until the host has joined once.

The response is the full meeting record including `invite_token`, `invite_link`,
`link_expires_at` and `recording_retention_days` (3).

### Invite
```json
{ "user_ids": [12, 34], "emails": ["partner@acme.com"], "send_email": true }
```
Registered users get an in-app/push notification **and** an email; email-only
invitees get the email. Duplicates are skipped, not errors:
```json
{ "invited": [ … ], "skipped": ["u1", "partner@acme.com"], "invite_link": "https://…/m/endwcue4fr6r" }
```

### Attendance
```json
{
  "attendees": [
    { "user_id": 5, "username": "adm", "full_name": "Ravi Menon",
      "is_guest": false, "is_host": true,
      "joined_at": "…", "left_at": null, "duration_seconds": null },
    { "user_id": null, "username": null, "full_name": "Asha Verma",
      "is_guest": true, "is_host": false,
      "joined_at": "…", "left_at": "…", "duration_seconds": 1840 }
  ],
  "recordings": [
    { "id": "…", "status": "READY", "started_at": "…", "ended_at": "…",
      "duration_seconds": 1920, "file_size_bytes": 84213760,
      "delete_after": "2026-10-01T…" }
  ]
}
```
Rows are written by LiveKit `participant_joined` / `participant_left` webhooks.

---

## 7. For signed-in users

```
GET /api/v1/meetings/my/
```
Open meetings the user hosts or was invited to, each with `invite_token`,
`is_host` and the same pre-join fields. Use it for an "Upcoming meetings" list.

---

## 8. Recording & retention

- Starts automatically when the **first participant joins** (LiveKit webhook) —
  there is no toggle and no "start recording" call.
- Written to the server's local `/recordings` volume as MP4.
- `delete_after` is set to **now + 3 days** at creation (normal consultation calls
  keep 15 days). The `cleanup_recordings` cron deletes the file and marks the row
  `DELETED`.
- Admins play/download from the existing **Recordings** page
  (`/api/v1/calls/admin/recordings/`).
- Tell participants: the pre-join screen and the invite email both state that the
  meeting is recorded and kept for 3 days.

---

## 9. Security notes

- Token is generated with `secrets.choice` over a 32-symbol alphabet, 12 chars.
- Links expire; `regenerate-link` revokes instantly (old token → 404).
- `INVITED_ONLY` reveals nothing — not even the title — without a login.
- A guest token is signed (not a JWT), expires in 6 hours, is scoped to one
  meeting, and opens only that meeting's chat socket. Verified: a guest token from
  meeting A cannot open meeting B's chat, and a tampered token resolves to nothing.
- Guest display names are sanitised (whitespace collapsed, non-printables stripped,
  60 chars).
- Only a meeting's admin/superadmin can list, edit, end, cancel or invite.
