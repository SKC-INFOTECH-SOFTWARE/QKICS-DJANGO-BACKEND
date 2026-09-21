# In-Feed Sponsored Cards — Mobile App Guide

Ads used to appear **only** in the desktop right sidebar. On phones (mobile web
and the app) there was no ad surface at all. The fix: an **in-feed sponsored
card after every 10th post**. This doc is the contract the mobile app should
follow so web and app behave identically.

> Backend already ships this. Nothing here needs a server change — just build
> the card and the injection rule. The web app implements exactly this in
> `frontend/src/components/hooks/useActiveAds.jsx` + `ui/FeedAdCard.jsx`.

---

## 1. Endpoint

```
GET /api/v1/ads/active/
GET /api/v1/ads/active/?placement=sidebar_featured   (optional filter)
```

- **Public** — works with or without a JWT.
- Returns a plain JSON **array** (no pagination) of ads that are `is_active`
  **and** whose `start_datetime <= now <= end_datetime`. Server does the time
  filtering; the app never checks dates.
- Empty array `[]` = no ads → render nothing, no error state.

```json
[
  {
    "id": 12,
    "uuid": "afc0e9ab-292f-40ea-8959-254c57be3ade",
    "title": "Grow your startup with Acme Cloud",
    "description": "Up to 100 words of copy. May contain newlines.",
    "media_type": "image",            // "image" | "video"
    "file_url": "https://api.example.com/media/ads/media/4efb….png",  // absolute
    "redirect_url": "https://acme.example/landing",
    "button_text": "Learn More",      // default "Learn More"; may be custom
    "placement": "sidebar_featured"
  }
]
```

Fetch it **once when the feed screen opens** (not per page). Cache in memory for
the screen's lifetime; refetch on pull-to-refresh along with the feed. Swallow
network errors silently (ad blockers / DNS filters commonly block this path) —
an ad failure must never break the feed.

---

## 2. Injection rule (must match web exactly)

Feed pages are `page_size = 10`, so "every 10th post" == one card per page.

```
ads       = result of GET /ads/active/   (may be [])
posts     = the flat list of feed posts rendered so far
hasMore   = feed has a next cursor OR a page is currently loading

for index, post in posts:
    position = index + 1                       # 1-based

    if position % 10 == 0:
        slot = position / 10 - 1               # 0 for post 10, 1 for post 20, …
        render ad card  ads[slot % len(ads)]   AFTER this post

    elif not hasMore and len(posts) < 10 and position == len(posts):
        render ad card  ads[0]                 AFTER this post   # short feed → 1 ad
```

Properties of this rule:
- Deterministic rotation: with 2 ads you get A, B, A, B… down the feed; with 1
  ad it repeats. The same ad never appears twice in a row when there are ≥2.
- A feed with <10 posts that has **finished loading** still shows one ad at the
  bottom. While it's still loading, nothing is shown (avoids a flash).
- `ads == []` → no cards anywhere, feed renders as before.
- Apply the rule on **Home feed** and **Knowledge Hub feed**. Do **not** inject
  into the immersive Videos feed.

Ad cards are **not** feed items: keep them out of the posts list/cursor state.
Render them in the list builder (e.g. `itemBuilder`) as an extra widget after
the post at that index, so likes/comments/scroll-restore indices stay correct.

---

## 3. Card spec

Same horizontal width and outer margins as a post card, so it "belongs" in the
feed. Top to bottom:

| Part            | Spec |
|-----------------|------|
| Label           | Small red dot + `SPONSORED` in tiny bold uppercase, muted colour. **Required** (ad transparency). |
| Media           | 16:9, rounded corners, `cover` fit. Tapping the media opens `redirect_url`. |
| — image         | `file_url`, lazy loaded. |
| — video         | `file_url`, autoplay, **muted by default**, loop, inline (no fullscreen takeover), no controls. Small mute/unmute toggle bottom-right. Don't preload the whole file (metadata / first frame only). |
| Title           | Bold, max **2 lines**, ellipsis. |
| Description     | Muted body text, clamped to **2 lines**. Below it a `SEE MORE ▼` link **only if the text actually overflows 2 lines**. Tapping expands the full text and the link becomes `SEE LESS ▲`. Preserve newlines. |
| Button          | Full-width primary (red) button, text = `button_text` (fallback `Learn More`), small external-link icon. Opens `redirect_url` in the system browser / in-app browser. |

If the media fails to load, **hide the whole card** (don't show a broken card).

Description is server-capped at **100 words**, so the expanded state is never
more than a few lines — no need for a scroll area.

---

## 4. Admin constraints (already enforced server-side)

For anyone building an admin screen in the app:

| Rule | Server response on violation |
|------|------------------------------|
| `description` ≤ 100 words (split on whitespace) | `400 {"description": ["Description must be at most 100 words (currently N)."]}` |
| `end_datetime` after `start_datetime` | `400 {"non_field_errors": ["End datetime must be after start datetime."]}` |
| File is a real image (jpg/png/gif/webp, validated by decoding) **or** a video with extension mp4/webm/mov/avi | `400 {"non_field_errors": ["Only image (jpg, png, gif, webp) and video (mp4, webm, mov, avi) files are allowed."]}` |
| File ≤ 50 MB | `400 {"non_field_errors": ["File size exceeds 50MB limit."]}` |

Admin endpoints (JWT with `user_type` admin/superadmin):

```
GET    /api/v1/admin/ads/                  list (paginated; ?search= ?placement= ?media_type= ?is_active= ?ordering=)
POST   /api/v1/admin/ads/create/           multipart: title, file, redirect_url, start_datetime, end_datetime,
                                            description?, button_text?, placement?, is_active (send "true"/"false" explicitly)
PATCH  /api/v1/admin/ads/<id>/             multipart, any subset of the above (omit file to keep current)
DELETE /api/v1/admin/ads/<id>/delete/
```

> Note for multipart: if `is_active` is **omitted** DRF treats it as `false`.
> Always send it.

---

## 5. Desktop behaviour (for reference)

Web at `≥ 1280px` keeps ads in the right sidebar only and hides the in-feed
card; below that the in-feed card is used. The same ad pool feeds both — one
campaign shows everywhere, admins don't create separate "mobile" ads.
