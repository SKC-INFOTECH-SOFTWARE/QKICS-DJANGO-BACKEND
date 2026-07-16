# Batch (Group) Video Calling — API Changes

**For:** Mobile app team
**Feature:** One expert can host a **group video call** — multiple users book the **same slot** (each pays a per-user price) and all join the **same** video call. The existing 1‑to‑1 expert↔user flow is **unchanged**; this only adds a new "batch" mode on top of it.

All endpoints are under `/api/v1/…` and use the existing JWT auth (`Authorization: Bearer <access>`). Nothing about auth, base URL, or the 1‑to‑1 flow changed.

> **TL;DR for mobile:** a slot now has a `slot_mode` of `ONE_TO_ONE` (old behaviour) or `BATCH` (new group video). Batch slots expose `capacity`, `batch_price`, `seats_left`, `is_batch_available`. Booking a batch slot is the same call as before; `session_type` is forced to `VIDEO_CALL`. All confirmed users + the expert join **one shared call room**, so the in‑call screen must render **N participants**, not just one.

---

## 1. Create a slot (expert) — NEW fields

`POST /api/v1/bookings/experts/slots/`

### One‑to‑one (unchanged)
```json
{
  "slot_mode": "ONE_TO_ONE",          // optional; default when omitted
  "start_datetime": "2026-08-01T10:00:00Z",
  "end_datetime": "2026-08-01T10:30:00Z",
  "duration_minutes": 30,
  "chat_price": 200,
  "video_call_price": 500,
  "requires_approval": true
}
```

### Batch / group video (NEW)
```json
{
  "slot_mode": "BATCH",
  "start_datetime": "2026-08-01T18:00:00Z",
  "end_datetime": "2026-08-01T19:00:00Z",
  "duration_minutes": 60,
  "capacity": 5,          // required: 2..10 (max 10)
  "batch_price": 200      // required: per-user price, > 0
}
```

Rules for `BATCH`:
- `capacity` — integer, **2 to 10** inclusive.
- `batch_price` — decimal, **> 0** (charged **per user**).
- `chat_price`, `video_call_price` are ignored (server forces them to `0`).
- `requires_approval` is ignored (server forces `false` → no approval step; user books & pays directly).
- Batch is **video only** (there is no group chat room).

Validation errors return `400` with a message, e.g. `{"capacity": ["Capacity must be between 2 and 10."]}`.

---

## 2. List an expert's slots — NEW response fields

`GET /api/v1/bookings/experts/<expert_uuid>/slots/`

Every slot object now includes these additional fields:

| Field | Type | Meaning |
|---|---|---|
| `slot_mode` | string | `"ONE_TO_ONE"` or `"BATCH"` |
| `capacity` | int | Max users (1 for one‑to‑one, 2–10 for batch) |
| `batch_price` | decimal string | Per‑user price (batch only; `"0.00"` otherwise) |
| `is_batch_available` | bool | `true` if a batch slot still has a free seat |
| `seats_left` | int | Remaining seats for a batch slot (`0` for one‑to‑one) |

Existing fields (`chat_price`, `video_call_price`, `is_chat_available`, `is_video_call_available`, etc.) are still present.

**Availability logic on the client:**
- One‑to‑one slot is bookable if `is_chat_available || is_video_call_available`.
- Batch slot is bookable if `is_batch_available` (equivalently `seats_left > 0`).
- A one‑to‑one slot disappears from the list once booked (as before). A batch slot **stays** in the list until all seats are taken.

Example batch slot in the response:
```json
{
  "uuid": "…",
  "slot_mode": "BATCH",
  "start_datetime": "2026-08-01T18:00:00Z",
  "end_datetime": "2026-08-01T19:00:00Z",
  "duration_minutes": 60,
  "capacity": 5,
  "batch_price": "200.00",
  "seats_left": 3,
  "is_batch_available": true,
  "chat_price": "0.00",
  "video_call_price": "0.00",
  "is_chat_available": false,
  "is_video_call_available": false
}
```

---

## 3. Create a booking — same endpoint, batch‑aware

`POST /api/v1/bookings/`

Request body is unchanged:
```json
{ "slot_id": "<slot_uuid>", "session_type": "VIDEO_CALL" }
```

For a **batch** slot:
- `session_type` is **forced to `VIDEO_CALL`** server‑side (send `"VIDEO_CALL"`).
- Price = the slot's `batch_price`.
- No approval → booking goes straight to `AWAITING_PAYMENT` (then pay to confirm).
- **Multiple different users** can book the same slot until it's full.
- A user can only book a given slot **once**.

New error cases (HTTP `400`, non‑field error string):
- `"This batch session is full."` — all seats taken (seats fill on a first‑come basis; capacity is enforced atomically on the server).
- `"You already have a booking for this slot."`

Response (unchanged shape) now also carries:

| Field | Type | Meaning |
|---|---|---|
| `is_batch` | bool | `true` for a batch booking |
| `slot_uuid` | string | The booked slot's UUID |
| `call_room_id` | string / null | The shared group call room (resolved from the slot for batch; may be `null` until the first confirmed booking creates it) |

---

## 4. Pay for the booking — unchanged

`POST /api/v1/payments/fake/booking/`
```json
{ "booking_id": "<booking_uuid>" }
```
Response `call_room_id` now works for batch bookings too (it resolves from the slot). After a successful payment the booking is `CONFIRMED` and the shared call room exists.

> Replace with the real payment gateway when integrated — the batch flow does not change how payment works, only that each user pays `batch_price`.

---

## 5. Join the video call — batch‑aware

`GET /api/v1/calls/<room_id>/`

Unchanged request. Returns the room detail plus a `livekit_token` + `livekit_url` to connect, exactly like 1‑to‑1.

Changes for batch rooms:
- **Access:** the expert (advisor) **or any user with a `CONFIRMED` booking on that slot** may fetch a token and join. (1‑to‑1 rooms are still limited to the two participants.)
- Response now includes `is_batch: true`.
- `user` may be `null` for a batch room (there is no single counterpart user — there are many). `advisor` is the expert.
- One **shared** `CallRoom` per batch slot: every confirmed user + the expert connect to the **same** LiveKit room.

`GET /api/v1/calls/my/` now also returns batch group rooms where the current user has a confirmed booking (previously only rooms where the user was the single `user` or `advisor`).

### Client video UI — important
The shared room can have **up to `capacity + 1` participants** (LiveKit `max_participants` is set to `capacity + 1`). The in‑call screen must handle **N remote participants** (a grid / gallery), not just one remote + self. In‑call text chat, notes, recording, and auto‑cut at the scheduled end all work the same as 1‑to‑1.

---

## 6. Booking lists — NEW field

`GET /api/v1/bookings/` and `GET /api/v1/bookings/?as_expert=true`

Each booking object now includes `is_batch` (bool). Use it to show a "Group" label and to know the join button opens a group call. `call_room_id` on a batch booking resolves from the slot.

---

## 7. In-call group features (LiveKit signalling + host mute)

These power the group-call UI (mic-mute indicator, raise hand, active speaker, host controls). Mobile should mirror them.

### Mic-mute indicator (client-side, LiveKit)
Use LiveKit's `TrackMuted` / `TrackUnmuted` events (source = microphone) plus each remote's audio-track presence to show a "muted" icon per participant. No backend call.

### Active speaker highlight (client-side, LiveKit)
Subscribe to `ActiveSpeakersChanged` — LiveKit gives the list of participants currently speaking. Ring/highlight their tiles.

### Raise hand & lower-all-hands (client-side, LiveKit data channel)
There is **no REST endpoint** for these — they use LiveKit's **data channel** (`publishData` / `DataReceived`, reliable). JSON payloads (UTF-8 encoded):

```json
{ "type": "raise_hand", "raised": true }     // a participant toggles their hand
{ "type": "lower_all_hands" }                 // host clears everyone's hand
```

On receive: update that participant's raised-hand state; on `lower_all_hands`, clear all (including self). The web app broadcasts to everyone (reliable). Keep the same `type` strings on mobile so web ↔ mobile interop works.

### Host force-mute — NEW REST endpoint

`POST /api/v1/calls/<room_id>/mute/`
```json
{ "identity": "<user_id>" }     // LiveKit identity == str(user.id)
```
- Only the **host** (the room's `advisor` / expert) may call it; others get `403`.
- Server force-mutes that participant's mic via the LiveKit server API (genuinely enforced, not cooperative). The muted user + everyone receive a `TrackMuted` event, so the mic-off indicator updates everywhere automatically.
- You can't mute yourself through this (use the local mic toggle); returns `400`.
- Response: `{ "muted": true|false }`.

### Host mute everyone — NEW REST endpoint

`POST /api/v1/calls/<room_id>/mute-all/`  (no body)
- Host only (`403` otherwise). Force-mutes every participant's mic except the host.
- Response: `{ "muted_count": <int> }`. Everyone's mic-off indicator updates via `TrackMuted`.

### Host remove participant — NEW REST endpoint

`POST /api/v1/calls/<room_id>/remove/`
```json
{ "identity": "<user_id>" }
```
- Host only (`403`). Disconnects that participant from the live call (they receive a LiveKit disconnect).
- Can't remove yourself (`400`). Response: `{ "removed": true|false }`.
- Note: this ends their current connection to the session. It does not permanently ban them from re-joining a still-active slot.

Determine "am I the host?" on the client by comparing your own user id (LiveKit `localParticipant.identity`) with the room's `advisor.id` from `GET /api/v1/calls/<room_id>/`.

---

## 8. Summary of what's new

| Area | Change |
|---|---|
| Slot create | `slot_mode`, `capacity`, `batch_price` accepted; batch forces video‑only + no approval |
| Slot list | `slot_mode`, `capacity`, `batch_price`, `is_batch_available`, `seats_left` added; batch slots stay until full |
| Booking create | Batch: video forced, per‑user price, no approval, multi‑user, "full" error; response has `is_batch`, `slot_uuid` |
| Booking list | `is_batch` added |
| Call detail / join | Batch access = expert or any confirmed user; `is_batch` in response; `user` can be null |
| My calls | Includes batch rooms the user is confirmed in |
| Video UI | Must render **N participants** (group grid) for batch rooms |
| Mic-mute indicator | Per participant, from LiveKit `TrackMuted`/`TrackUnmuted` (client-side) |
| Active speaker | Highlight tile via LiveKit `ActiveSpeakersChanged` (client-side) |
| Raise hand / lower all | LiveKit data channel messages `raise_hand` / `lower_all_hands` (client-side, no REST) |
| Host force-mute | **NEW** `POST /calls/<room_id>/mute/` `{identity}` — expert only, server-enforced |
| Host mute everyone | **NEW** `POST /calls/<room_id>/mute-all/` — expert only |
| Host remove participant | **NEW** `POST /calls/<room_id>/remove/` `{identity}` — expert only |

Nothing was removed and no existing field changed meaning — all additions are backward‑compatible. Existing 1‑to‑1 clients keep working unchanged.
