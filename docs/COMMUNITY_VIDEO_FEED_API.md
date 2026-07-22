# Community Video Feed — API Changes

**For:** Mobile app team
**Feature:** An immersive, scroll-through **video feed** (Instagram Reels / Facebook Watch style). Tapping any video in the community feed opens a full-screen vertical feed that plays videos one at a time. From a **user's profile**, the feed is scoped to **only that user's videos**. Nothing about the existing community feed, likes, or comments changed — this only adds **one new read endpoint** plus **one optional query param**.

All endpoints are under `/api/v1/…` and use the existing JWT auth (`Authorization: Bearer <access>`). The endpoint is `IsAuthenticatedOrReadOnly`, so **guests can read it** too (no token → global feed still works).

> **TL;DR for mobile:** call `GET /api/v1/community/posts/videos/` for the global video feed, or `…/videos/?user=<username>` for a single user's video feed. Response shape is **identical to the normal feed** (`GET /api/v1/community/posts/`) — cursor-paginated list of `Post` objects, but filtered to posts that contain at least one video. Like/comment reuse the existing post endpoints, no change.

---

## 1. Video feed — NEW endpoint

`GET /api/v1/community/posts/videos/`

Returns only posts that contain **at least one video** (`media[].media_type == "video"`), **newest first**, cursor-paginated (same as the main feed).

### Query params

| Param | Type | Required | Meaning |
|---|---|---|---|
| `user` | string (username) | optional | Scope the feed to **one user's** videos only. Omit for the global feed. |
| `cursor` | string | optional | Pagination cursor — **use the `next` URL from the previous response as-is**; don't build it by hand. |

**Examples**
```
GET /api/v1/community/posts/videos/                 → global video feed
GET /api/v1/community/posts/videos/?user=johndoe    → only johndoe's videos
```

> When you follow the `next` link, the `user` filter is **preserved automatically** — the `next` URL already carries both `user` and `cursor`. Just GET it verbatim.

### Response — `200 OK`

Same envelope and object shape as `GET /api/v1/community/posts/` (cursor pagination):

```json
{
  "next": "https://api.example.com/api/v1/community/posts/videos/?cursor=cD0yMDI2...",
  "previous": null,
  "results": [
    {
      "id": 128,
      "author": {
        "id": 42,
        "username": "johndoe",
        "first_name": "John",
        "last_name": "Doe",
        "user_type": "expert",
        "user_type_display": "Expert",
        "profile_picture": "https://.../media/profile_pics/42.jpg"
      },
      "title": "My pitch",
      "content": "Watch this…",
      "media": [
        {
          "id": 301,
          "media_type": "video",
          "file": "https://.../media/post_media/clip.mp4",
          "order": 0,
          "created_at": "2026-07-20T09:00:00Z"
        }
      ],
      "tags": [],
      "knowledge_hub": false,
      "total_likes": 12,
      "total_comments": 3,
      "is_liked": false,
      "is_locked": false,
      "preview_length": 300,
      "full_length": 812,
      "created_at": "2026-07-20T09:00:00Z",
      "updated_at": "2026-07-20T09:00:00Z"
    }
  ]
}
```

**Notes on the shape (unchanged from the normal feed, listed for convenience):**
- `media` is an array. A post may contain **images and videos mixed**; this feed only guarantees **≥1** item has `media_type == "video"`. On the video screen, play the **first** `media` item where `media_type == "video"`.
- `media_type` ∈ `"image"` | `"video"`. `file` is a fully-qualified URL.
- `is_liked` — whether the current user liked it (always `false` for guests).
- `total_likes` / `total_comments` — counters to render on the action rail.
- `content` is **subscription-gated**: non-premium/non-author users get the preview text only (`preview_length` chars). Same rule as the normal feed.

### Empty / edge cases
- No videos at all → `{ "next": null, "previous": null, "results": [] }`.
- `?user=<unknown>` → empty `results` (no 404; just an empty feed).

---

## 2. Behaviour to replicate on the client (UX contract)

The backend only filters + paginates. These are **client-side** rules the web app follows; mobile should match them so the experience is consistent:

1. **Open the tapped video first.** When the user taps a specific video, open the immersive feed **anchored on that post**. Because the feed is paginated (10/page, newest first), the tapped post may **not** be on the first page. So:
   - Load page 1 of `…/videos/` (add `?user=` if opened from a profile).
   - If the tapped `post.id` is **not** in that page, fetch it directly via `GET /api/v1/community/posts/<id>/` and **pin it to the front** of your list.
   - If it **is** already in the page, just move it to the front.
   - Then keep loading more pages on scroll. **De-dupe by `post.id`** so the pinned post doesn't reappear.

2. **Profile-scoped vs global.**
   - Opened from a **profile** → pass `?user=<that profile's username>` → feed shows only their videos.
   - Opened from the **home / search / knowledge-hub** feed → no `user` param → global feed.

3. **Autoplay & one-at-a-time.** Autoplay the visible video **with sound**; if the OS blocks unmuted autoplay before a user gesture, fall back to muted and retry. Only one video plays at a time (pause the rest as they scroll off-screen).

---

## 3. Like & comment — REUSE existing endpoints (no change)

The video feed does **not** add its own like/comment APIs. Use the same ones as the normal community feed:

| Action | Method + endpoint |
|---|---|
| Like / unlike a post | `POST /api/v1/community/posts/<post_id>/like/` (toggles) |
| List comments | `GET /api/v1/community/posts/<post_id>/comments/` |
| Add a comment | `POST /api/v1/community/posts/<post_id>/comments/` |
| List replies | `GET /api/v1/community/comments/<comment_id>/replies/` |
| Add a reply | `POST /api/v1/community/comments/<comment_id>/replies/` |
| Like / unlike a comment | `POST /api/v1/community/comments/<comment_id>/like/` (toggles) |
| Delete own comment | `DELETE /api/v1/community/comments/<comment_id>/` |
| Delete own reply | `DELETE /api/v1/community/replies/<reply_id>/` |

After a like/comment, update the card's `is_liked` / `total_likes` / `total_comments` locally (the like toggle response returns the fresh state under `data`).

---

## 4. Summary of what's new

| Change | Detail |
|---|---|
| **New endpoint** | `GET /api/v1/community/posts/videos/` — video-only posts, newest first, cursor-paginated. |
| **New optional param** | `?user=<username>` on that endpoint → single-user (profile) video feed. `cursor` param preserves it. |
| **No new** | serializer
, auth, like, or comment changes. Response = same `Post` shape as `GET /api/v1/community/posts/`. |
