# PayU Payment Integration — API Guide (Web + Mobile)

This backend uses a **gateway-agnostic** payment layer. Clients never talk to
PayU directly for the decision-making — they call our generic endpoints and
**follow the `flow` field** the backend returns. Switching gateways later
(Razorpay/Stripe/etc.) is a backend-only change; these endpoints stay the same.

- Live gateway is chosen by the backend env var `PAYMENT_GATEWAY`
  (`fake` = instant/dev, `payu` = hosted checkout).
- Amounts are **always computed server-side** — clients never send an amount.
- Hashes are generated **only** on the server (Key/Salt never reach the client).

All endpoints are under `/api/v1/payments/` and require the JWT `Authorization`
header, **except** the PayU callbacks/webhook (called by PayU, not the client).

---

## 1. Initiate a payment  →  `POST /api/v1/payments/initiate/`

One endpoint for **both** bookings and subscriptions.

**Request (booking):**
```json
{ "purpose": "BOOKING", "booking_id": "<booking-uuid>" }
```
**Request (subscription):**
```json
{ "purpose": "SUBSCRIPTION", "plan_uuid": "<plan-uuid>" }
```

> For a booking, create the booking first (`POST /api/v1/bookings/…`) and pass
> its `uuid` here. The server reads the price from the booking/plan itself.

**Response A — instant gateway (`fake`, dev):** payment already done.
```json
{
  "flow": "instant",
  "payment": { "uuid": "...", "status": "SUCCESS", "purpose": "BOOKING", ... },
  "result": { "booking_id": "...", "chat_room_id": null, "call_room_id": "..." }
}
```
Nothing more to do — for a booking, `result` carries the room ids.

**Response B — hosted checkout (`payu`):** you must send the user to PayU.
```json
{
  "flow": "redirect_post",
  "payment": { "uuid": "...", "status": "INITIATED", ... },
  "checkout": {
    "action_url": "https://test.payu.in/_payment",
    "params": {
      "key": "...", "txnid": "...", "amount": "100.00",
      "productinfo": "BOOKING:<ref-uuid>", "firstname": "...", "email": "...",
      "phone": "...", "surl": "...", "furl": "...", "udf1": "<payment-uuid>",
      "hash": "<sha512 signed by server>"
    }
  }
}
```

**Always branch on `flow`.** Never hardcode "payu" — an instant gateway skips
the whole redirect.

---

## 2. Web flow (redirect_post)

Auto-submit `checkout.params` as an HTML form POST to `checkout.action_url`.
The browser goes to PayU, the user pays, and PayU redirects back to our
`surl`/`furl`, which then redirect the browser to:

```
<FRONTEND_URL>/payment/result?status=success|failed&payment=<payment-uuid>
```

The result page polls **`GET /api/v1/payments/status/<payment-uuid>/`** until the
status is `SUCCESS`/`FAILED`, then shows the outcome. (Already implemented in
`src/pages/PaymentResult.jsx` + `src/components/utils/paymentApi.js`.)

---

## 3. Mobile app flow (PayU Checkout Pro SDK)

The **same** `/initiate/` endpoint serves the app — no separate hash endpoint.

1. Call `POST /initiate/` with the purpose + reference.
2. If `flow === "instant"` → done (dev/fake).
3. If `flow === "redirect_post"` → feed `checkout.params` to the **PayU
   Checkout Pro** SDK (Android/iOS/Flutter). The SDK already has everything it
   needs: `key`, `txnid`, `amount`, `productinfo`, `firstname`, `email`,
   `phone`, `udf1`, `surl`, `furl`, and the server-generated `hash`.
   - **Do not** compute the hash on-device. Use the `hash` we return.
   - `surl`/`furl` point at our backend; the SDK's success/failure callbacks
     also fire locally — use whichever your SDK gives you.
4. After the SDK returns, call
   **`GET /api/v1/payments/status/<payment-uuid>/`** to get the authoritative
   result (the backend is confirmed independently via callback/webhook, so
   trust the server, not the on-device callback).

> Environment: `action_url` host (`test.payu.in` vs `secure.payu.in`) tells the
> SDK which environment to use. Prefer reading it from our response rather than
> hardcoding.

---

## 4. Endpoints called by PayU (not the client — for reference only)

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/payments/payu/callback/success/` | PayU `surl`. Verifies reverse hash, confirms booking/subscription, redirects browser to the frontend result page. |
| `POST /api/v1/payments/payu/callback/failure/` | PayU `furl`. Same verification; marks failed. |
| `POST /api/v1/payments/payu/webhook/` | Optional server-to-server confirmation. Idempotent. |

The server **verifies the PayU reverse hash** before trusting any status, and
fulfilment (confirm booking / activate subscription) is **idempotent** — a
webhook and a redirect arriving together will not double-confirm.

---

## 5. Status endpoint  →  `GET /api/v1/payments/status/<payment-uuid>/`

```json
{
  "uuid": "...", "purpose": "BOOKING", "amount": "100.00",
  "status": "SUCCESS", "gateway": "PAYU",
  "result": { "booking_id": "...", "chat_room_id": null, "call_room_id": "..." }
}
```
`result` is present for confirmed **bookings**. Poll this after returning from
the gateway; treat `SUCCESS`/`FAILED` as terminal.

---

## 6. Summary for the app team

- Call `/initiate/`, then **switch on `flow`** (`instant` vs `redirect_post`).
- For `redirect_post`, pass `checkout.params` straight into the PayU SDK —
  **hash is already signed by the server**.
- Confirm the outcome via `/status/<uuid>/`; the server is the source of truth.
- The client is gateway-blind: if we swap PayU for another gateway, this
  contract does not change (only the `action_url`/params shape the SDK consumes).
