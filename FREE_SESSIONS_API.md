# Free Sessions (Chat / Video / Group) — Mobile App Guide

Experts can now offer a session **free of charge**. A free option has price `0`
but is still bookable, and **booking it skips payment entirely** — the booking is
confirmed with no gateway step. This doc is the contract the mobile app should
follow to add the same behaviour.

> Backend already ships this. Nothing here needs a server change — just build the
> app screens to send/read the new fields.

---

## 1. What changed on the model

`ExpertSlot` gained three booleans:

| Field                 | Applies to        | Meaning                                  |
|-----------------------|-------------------|------------------------------------------|
| `is_chat_free`        | one-to-one        | Chat is free (price forced to `0`)       |
| `is_video_call_free`  | one-to-one        | Video call is free (price forced to `0`) |
| `is_batch_free`       | batch (group)     | Group call is free (price forced to `0`) |

Rule: **`price == 0` alone means "disabled"**. An option is only *available* when
`price > 0` **OR** its `*_free` flag is `true`. The server enforces this; the app
must send the flag, not just a `0` price.

---

## 2. Expert: creating / editing a slot

Endpoints (unchanged):
- Create: `POST /api/v1/bookings/experts/slots/`
- Update: `PATCH /api/v1/bookings/experts/slots/<uuid>/`

### One-to-one payload

Add a **"Free"** checkbox next to each price field (Chat and Video). When ticked,
hide the price input and send the flag `true` with price `0`.

```jsonc
// One-to-one, chat is FREE, video is paid ₹500
{
  "slot_mode": "ONE_TO_ONE",
  "start_datetime": "2026-09-01T10:00:00Z",
  "end_datetime": "2026-09-01T10:30:00Z",
  "duration_minutes": 30,
  "chat_price": 0,
  "is_chat_free": true,
  "video_call_price": 500,
  "is_video_call_free": false,
  "requires_approval": true
}
```

### Batch (group video) payload

One **"Make this group call free"** checkbox. When ticked, hide the per-user price
and send `is_batch_free: true` with `batch_price: 0`.

```jsonc
{
  "slot_mode": "BATCH",
  "start_datetime": "2026-09-01T18:00:00Z",
  "end_datetime": "2026-09-01T18:45:00Z",
  "duration_minutes": 45,
  "capacity": 10,
  "batch_price": 0,
  "is_batch_free": true
}
```

### Validation (server-side; mirror on the client for nicer UX)
- One-to-one: at least one of Chat / Video must be **enabled** — i.e.
  `is_chat_free` OR `chat_price > 0` OR `is_video_call_free` OR `video_call_price > 0`.
- Batch: `is_batch_free` **or** `batch_price > 0` (plus `2 ≤ capacity ≤ 80`).
- "Free" wins over any typed price — the server forces that price to `0`.

---

## 3. Reading a slot

`GET /api/v1/bookings/experts/<expert_uuid>/slots/` and every slot serializer now
return the three flags plus the existing availability booleans:

```jsonc
{
  "uuid": "…",
  "slot_mode": "ONE_TO_ONE",
  "chat_price": "0.00",
  "video_call_price": "500.00",
  "is_chat_free": true,
  "is_video_call_free": false,
  "is_batch_free": false,
  "batch_price": "0.00",
  "is_chat_available": true,        // already true for a free-and-unbooked option
  "is_video_call_available": true,
  "is_batch_available": false,
  "seats_left": 0
}
```

Display rule in the app: **show "Free" (not "₹0" / "N/A")** whenever the matching
`*_free` flag is `true`. An option is offered when `is_*_free || price > 0`.

---

## 4. User: booking a free session

Booking endpoint is unchanged:
`POST /api/v1/bookings/` → body `{ "slot_id": "<uuid>", "session_type": "CHAT" | "VIDEO_CALL" }`
(batch forces `VIDEO_CALL` automatically).

**The difference is what you do with the response.** Decide "is this free?" on the
client from the chosen option's price/flag:

```
isFree = (chosen option price <= 0)   // == the *_free flag is set
```

### Flow when `isFree == true`  → **do NOT call the payment endpoint**

1. `POST /api/v1/bookings/` to create the booking.
2. Look at the returned `status`:
   - `"CONFIRMED"` → done. Session is booked & the room/chat is provisioned. Show
     "Booking confirmed — it's free!". Read `call_room_id` / `chat_room_id` from
     the booking just like a paid confirmed booking.
   - `"PENDING"` → the expert requires approval. Show "Request sent. Awaiting expert
     approval." The booking confirms automatically when the expert approves (no
     payment ever). Poll the booking or refresh the list to see it flip to
     `CONFIRMED`.
3. **Never** call `POST /api/v1/payments/initiate/` for a free booking — the server
   returns `400 "This is a free session; no payment is required."`

### Flow when `isFree == false` → unchanged
Create booking → `POST /payments/initiate/` → follow `flow` (`redirect_post` for
PayU hosted checkout, `instant` for the fake gateway). See
[`PAYU_PAYMENT_INTEGRATION.md`](PAYU_PAYMENT_INTEGRATION.md).

---

## 5. Status cheat-sheet

| Slot                         | On booking create        | After expert approves | Payment |
|------------------------------|--------------------------|-----------------------|---------|
| Paid, approval required      | `PENDING`                | `AWAITING_PAYMENT`    | Yes     |
| Paid, no approval            | `AWAITING_PAYMENT`       | —                     | Yes     |
| **Free, approval required**  | `PENDING`                | `CONFIRMED`           | **No**  |
| **Free, no approval**        | `CONFIRMED` (immediately)| —                     | **No**  |
| Batch paid (never approval)  | `AWAITING_PAYMENT`       | —                     | Yes     |
| **Batch free**               | `CONFIRMED` (immediately)| —                     | **No**  |

A `CONFIRMED` free booking exposes `chat_room_id` (chat) or `call_room_id` (video /
group) exactly like a paid one — join the same way.

---

## 6. Quick checklist for the app

- [ ] Slot editor: "Free" checkbox on Chat, Video, and Group price fields; hide the
      price input when ticked; send `is_*_free: true` + price `0`.
- [ ] Slot cards / booking list: render **"Free"** when the flag is set.
- [ ] Booking screen: compute `isFree`; when free, skip the payment call and branch
      on the returned `status` (`CONFIRMED` vs `PENDING`).
- [ ] Confirm dialog / button copy: "Confirm Booking" (free) vs "Confirm & Pay".
