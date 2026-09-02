# Auth Email OTP — Mobile App Guide

Two email-OTP flows were added. Build the same screens in the app.

1. **Registration email verification** — the user's email is verified with a
   6-digit OTP **before** the account is created. No unverified/half-created
   accounts.
2. **Forgot password** — the user resets a forgotten password with an OTP sent
   to their email.

A **welcome email** ("You have successfully registered in Qkics") is also sent
automatically on successful registration — nothing for the app to do there.

> Backend already ships this. All endpoints are under `/api/v1/auth/`.
> OTP: **6 digits**, expires in **10 minutes**, max **5 wrong attempts**, resend
> cooldown **60s**, max **5 codes/hour** per email+purpose.

---

## 1. Registration flow (verify-before-register)

### Step 1 — send verification code
`POST /api/v1/auth/register/send-otp/`
```jsonc
{ "email": "user@example.com" }
```
- **200** `{ "message": "Verification code sent to your email." }`
- **400** `{ "email": ["This email is already registered."] }` — email taken.
- **429** `{ "error": "...", "code": "cooldown" | "rate_limited" }` — throttled;
  show the message, keep the user on the code screen.

### Step 2 — verify the code
`POST /api/v1/auth/register/verify-otp/`
```jsonc
{ "email": "user@example.com", "code": "123456" }
```
- **200** `{ "message": "...", "verified": true }`
- **400** `{ "error": "Incorrect code. Please try again.", "code": "invalid" }`
  (other `code`s: `expired`, `too_many_attempts`, `not_found` → request a new code)

### Step 3 — create the account (existing endpoint, now gated)
`POST /api/v1/auth/register/`
```jsonc
{
  "username": "johndoe",
  "email": "user@example.com",
  "password": "secret123",
  "password2": "secret123",
  "phone": "9876543210",
  "user_type": "normal"
}
```
- **201** → account created; log in normally afterwards.
- **400** `{ "email": "Please verify your email with the OTP first." }` — the
  email wasn't verified (Step 2 not done, or the 15-minute verified window
  elapsed → re-run Steps 1–2).

**Recommended UX:** one form for the details, then a second screen for the code.
Only call `register/` after `verify-otp/` succeeds. The verified email stays
valid for **15 minutes** to complete registration.

---

## 2. Forgot-password flow

### Step 1 — request a reset code
`POST /api/v1/auth/password/forgot/`
```jsonc
{ "email": "user@example.com" }
```
- **Always 200** `{ "message": "If that email is registered, a reset code has been sent." }`
  — the response is intentionally generic (no "user not found") to avoid leaking
  which emails exist. Move to the code screen regardless.

### Step 2 (optional) — pre-check the code
`POST /api/v1/auth/password/verify-otp/`
```jsonc
{ "email": "user@example.com", "code": "123456" }
```
- **200** `{ "valid": true }` — code is good (NOT consumed; the reset call still
  needs it). Use this only if you want to validate before showing the
  new-password field.
- **400** `{ "error": "...", "code": "invalid" | "expired" | ... }`

### Step 3 — reset the password
`POST /api/v1/auth/password/reset/`
```jsonc
{
  "email": "user@example.com",
  "code": "123456",
  "new_password": "myNewPass123"
}
```
- **200** `{ "message": "Password reset successful. You can now log in." }`
- **400** `{ "error": "..." }` — wrong/expired code, or `new_password` failed
  validation (`{ "new_password": ["This password is too short."] }`).

The code is **single-use** — consumed on a successful reset. A "password
changed" security notification is sent automatically.

---

## 3. Error `code` cheat-sheet

| `code`              | Meaning                              | App action                    |
|---------------------|--------------------------------------|-------------------------------|
| `cooldown`          | Resent too soon (<60s)               | Show wait message, disable resend briefly |
| `rate_limited`      | >5 codes in the last hour            | Ask user to try later         |
| `invalid`           | Wrong code                           | Let them retry (attempts left)|
| `too_many_attempts` | 5 wrong tries                        | Force "Resend code"           |
| `expired`           | Code older than 10 min               | Force "Resend code"           |
| `not_found`         | No active code for this email        | Force "Resend code"           |

---

## 4. Quick checklist for the app

- [ ] Signup: details screen → **Send code** → code screen → **Verify** →
      create account → login. Add a **Resend code** button (respect the 60s
      cooldown message).
- [ ] Login screen: **"Forgot password?"** link → email → code + new password.
- [ ] Treat `password/forgot/` as always-200; never tell the user whether the
      email exists.
- [ ] Surface the `error` message from 400/429 responses; branch on `code`
      where useful (see cheat-sheet).
- [ ] Numeric 6-digit input; trim/strip non-digits.
