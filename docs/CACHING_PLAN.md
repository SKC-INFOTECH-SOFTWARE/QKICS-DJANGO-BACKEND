# Caching & Query-Performance Plan

**Status:** Phase 0 and Phase 1.1 **implemented** (2026-07-23); Phases 1.2 onward proposed
**Scope:** backend (`rplatform`) — no public API contract changes
**Author:** architecture review, 2026-07-23

> Measured after Phase 0: serializing a feed page costs **3 queries at any page size**
> (1, 5 and 10 posts all measured at 3), and **1** `UserSubscription` lookup per request
> instead of ~20. Verified against a throwaway sqlite DB, comparing every annotation to
> the old property/`exists()` result — all matched.

---

## 1. Current state (measured from the code)

| Fact | Evidence |
|---|---|
| Redis cache backend **is configured** | `rplatform/settings/production.py:88-93` (`RedisCache`, db `0`) |
| Cache framework is **used nowhere** | zero hits for `cache.get` / `cache.set` / `cache_page` / `from django.core.cache` across all `*.py` |
| Dev/base settings define **no** `CACHES` | `rplatform/settings/base.py` — dev silently falls back to `LocMemCache` |
| Cache and channel layer **share Redis db 0** | `CACHES` → `/0`; `CHANNEL_LAYERS` (`base.py:201`) uses `channels_redis` default db `0` |

So: the plumbing exists, nothing flows through it.

### 1.1 The bigger problem — N+1 before caching

A single community feed page (`PostCursorPagination` = 10 posts) issues roughly **40+ extra queries**
on top of the base query:

| Cost | Per post | Source |
|---|---|---|
| `total_likes` → `self.post_likes.count()` | 1 query | `community/models.py:82` (model `@property`, exposed as `IntegerField`) |
| `is_liked` → `.filter(user=...).exists()` | 1 query | `community/serializers.py:114, 187, 260, 329` — defeats the existing `prefetch_related("post_likes")` |
| `is_user_premium(user)` in `get_content` | 1 query | `community/serializers.py:90, 162, 252, 324` |
| `is_user_premium(user)` in `get_is_locked` | 1 query | `community/serializers.py:102, 174, 271` |

`is_user_premium()` (`subscriptions/services/access.py:26`) hits `UserSubscription` every call and is
**not memoised** — the same user's subscription is looked up ~20 times to render one page.

> **Rule for this plan: fix the queries first, then cache.** Caching an N+1 just caches slowness,
> and every cache miss stays as slow as today.

### 1.2 Other hot spots found

| Endpoint | Problem | File |
|---|---|---|
| `GET /admin/dashboard/stats/` | ~12 aggregates + two 6-month `TruncMonth` series + recent-users, **every request** | `adminpanel/views/dashboard.py:24-122` |
| `GET /community/tags/` | `Tag.objects.all()` unpaginated, serialized on every request; the search sidebar calls it on mount | `community/views.py:61-66` |
| `GET /community/search/` | LIKE-scan fallback when the FULLTEXT index is absent | `community/views.py` (`SearchPostsView`) |
| Feeds (`posts/`, `posts/videos/`, `knowledge-hub/`) | re-query + re-serialize identical rows for every user | `community/views.py:111, 563`, `PostVideoFeedView` |

---

## 2. Design principles

1. **Cache what is shared, expensive, and tolerant of staleness.** Never cache what is per-user and
   cheap to derive.
2. **Never cache a serialized post response.** `content`, `is_locked`, and `is_liked` are per-user —
   caching the rendered payload would leak premium content across users. Cache the **ID list**
   instead, then hydrate + serialize per request.
3. **Prefer the database over Redis for counts.** An annotation is exact and free; a cached count is
   approximate and needs invalidation.
4. **TTL-first invalidation.** Explicit invalidation only where staleness is user-visible (tags, premium status).
5. **Every cache must be bypassable.** One flag turns the whole layer off.

---

## 3. Phased plan

### Phase 0 — Kill the N+1 (no caching) — ✅ DONE

*Highest impact, lowest risk. Do this even if nothing else ships.*

Shipped as described below, with two deviations worth recording:

- Counts use **correlated subqueries** (`_related_count()` in `community/views.py`), not
  `Count(..., distinct=True)`. Two `Count()` annotations in one query join both relations and
  produce a cartesian row set (a post with 100 comments and 100 likes scans 10 000 rows);
  a subquery per relation avoids the join entirely and leaves the outer query without a `GROUP BY`.
- Comments and replies got the same treatment (`get_optimized_comment_queryset()`), which also
  fixed a latent crash: `LikeToggleView` returned an unannotated `Comment` to `CommentSerializer`,
  whose `total_replies` field reads `source="total_replies_count"` — an annotation-only attribute.
  Liking a top-level comment would raise `AttributeError`.

**0.1 Annotate likes + is_liked in the shared queryset** (`community/views.py:48`)

```python
def get_optimized_post_queryset(user=None):
    qs = (
        Post.objects.select_related("author")
        .prefetch_related("tags", "media")           # post_likes prefetch no longer needed
        .annotate(
            total_comments_count=Count("comments", distinct=True),
            likes_count=Count("post_likes", distinct=True),
        )
    )
    if user is not None and user.is_authenticated:
        qs = qs.annotate(
            is_liked_ann=Exists(
                PostLike.objects.filter(post=OuterRef("pk"), user=user)
            )
        )
    return qs
```

**0.2 Serializers read the annotation, fall back to the property**

`total_likes` is a model `@property`, i.e. a data descriptor — an annotation named `total_likes`
would raise on assignment. Use a distinct annotation name and read it defensively so
non-annotated code paths (detail views, nested serializers) keep working:

```python
total_likes = serializers.SerializerMethodField()

def get_total_likes(self, obj):
    v = getattr(obj, "likes_count", None)
    return v if v is not None else obj.total_likes      # fallback = old behaviour

def get_is_liked(self, obj):
    v = getattr(obj, "is_liked_ann", None)
    if v is not None:
        return v
    user = self.context["request"].user
    return user.is_authenticated and obj.post_likes.filter(user=user).exists()
```

Apply the same shape to all four post/comment serializers
(`community/serializers.py:114, 187, 260, 329`).

**0.3 Memoise `is_user_premium` per request**

Two layers:

- *Per request* — resolve once in the view / serializer `__init__` and pass through context, so
  `get_content` and `get_is_locked` never hit the DB twice for the same object.
- *Per user, cross request* — Redis, in Phase 1 (§3.2.3).

**Expected result:** ~43 queries per feed page → **3**.
Verify with `assertNumQueries` in a test before/after.

---

### Phase 1 — Wire up the cache layer

**1.1 Settings hygiene** — ✅ DONE (a correctness fix, not an optimisation)

- Move the cache to **Redis db `1`**. Today `CACHES` and `CHANNEL_LAYERS` both use db `0`; a single
  `cache.clear()` would flush live channel-layer state and drop in-flight WebSocket messages.
- Add `KEY_PREFIX: "qkics"` and `TIMEOUT: 300` to `CACHES["default"]`.
- Define `CACHES` in `base.py` (dev → `LocMemCache`) so cache-using code behaves identically locally.
- Add `CACHE_ENABLED = config("CACHE_ENABLED", default=True, cast=bool)` — the global off-switch.

**1.2 A small cache helper** — new `rplatform/cache.py` *(next up)*

```python
def cached(key, ttl, producer, jitter=0.1):
    """get_or_set with a global kill-switch and TTL jitter (anti-stampede)."""
```

Plus `bump_version(namespace)` for namespace-based invalidation (`tags:v3:*`), which avoids
key-scanning on Redis.

**1.3 First cache targets** — shared, expensive, staleness-tolerant

| Target | Key | TTL | Invalidation |
|---|---|---|---|
| `AdminDashboardStatsView` | `admin:dashboard:stats` | 10 min | TTL only |
| `TagListCreateView.get` | `community:tags:v{n}` | 1 h | version bump on tag create |
| Subscription plans list | `subs:plans:v{n}` | 1 h | version bump on plan change |
| `is_user_premium(user)` | `user:{id}:premium` | 5 min | delete on subscribe / cancel / payment webhook |

The dashboard alone turns ~15 aggregate queries into one Redis `GET` for every admin page load.

**Caution on `user:{id}:premium`:** it gates paid content, so the invalidation hooks are mandatory —
a user who just paid must not wait 5 minutes. Delete the key in the PayU success handler and in
`UserSubscription` `post_save`/`post_delete`. TTL is the safety net, not the mechanism.

---

### Phase 2 — Feed & search result caching (ID lists only)

Cache the **ordered list of post IDs** for a given query + cursor; hydrate through
`get_optimized_post_queryset()` and serialize per request. Per-user fields stay correct.

| Target | Key | TTL |
|---|---|---|
| Search posts | `search:posts:{sha1(q)}:{cursor}` | 60 s |
| Global feed, first page | `feed:posts:p1` | 30 s |
| Video feed, first page (global + per user) | `feed:videos:{user or "all"}:p1` | 60 s |

Only page 1 is worth caching — deep cursors have a long tail and near-zero hit rate.

**Note:** search is currently returning 500 in production. That is a **missing FULLTEXT index**
issue, not a caching issue (see `docs`/memory `search-system`). Caching must not be used to paper
over it — fix the index first, then cache.

---

### Phase 3 — Edge caching (Cloudflare, already in front of prod)

For endpoints reachable anonymously (`IsAuthenticatedOrReadOnly`) send real cache headers:

```
Cache-Control: public, max-age=30, stale-while-revalidate=120
```

Candidates: public feed, tags, experts/companies listings, public company profiles.

**Hard requirement:** add `Vary: Authorization` (and `Cookie`) so an authenticated response is never
served to an anonymous visitor or vice-versa. If that cannot be guaranteed for an endpoint, do not
edge-cache it — Phase 2 already covers the origin cost.

---

### Phase 4 — Denormalised counters (only when volume demands it)

`Count()` per feed page stops scaling once posts have thousands of likes.

- Add `likes_count` / `comments_count` integer columns on `Post`.
- Update with `F("likes_count") + 1` inside the like/unlike transaction.
- Backfill via a data migration; keep the annotation path until the backfill is verified.

Do **not** start here. Phase 0 is enough for current volume.

---

## 4. Invalidation summary

| Data | Strategy | Trigger |
|---|---|---|
| Dashboard stats | TTL 10 min | — |
| Tags / plans | version bump | create / update / delete signal |
| Premium status | explicit delete + TTL 5 min | subscription save/delete, payment webhook |
| Feed / search ID lists | short TTL | — (new post appears within 30–60 s) |
| Edge cache | TTL + `Vary` | — |

Never invalidate with `cache.clear()` — it is db-wide (see §3.1.1).

---

## 5. Rollout order & exit criteria

| Step | Work | Exit criterion |
|---|---|---|
| 1 | Phase 0 (query fixes) | `assertNumQueries` on the feed drops from ~43 to ≤5 |
| 2 | Phase 1.1 settings hygiene | cache on db 1, `CACHE_ENABLED` toggles cleanly |
| 3 | Phase 1.3 dashboard + tags + premium | dashboard p95 under 100 ms warm |
| 4 | Phase 2 search/feed ID lists | search p95 improves; results still per-user correct |
| 5 | Phase 3 edge headers | origin request volume drops for anonymous traffic |
| 6 | Phase 4 | only if likes/comments per post exceed ~10k |

Steps 1–3 deliver the large majority of the benefit. Steps 4–6 are demand-driven.

## 6. Risks

- **Premium content leak** — mitigated by never caching serialized post payloads (§2.2) and by
  explicit `user:{id}:premium` invalidation (§3.1.3).
- **Stale admin numbers** — accepted, 10 min; document it in the admin UI if it confuses anyone.
- **Redis becomes a single point of failure** — cache helper must swallow Redis errors and fall
  through to the producer, never 500. Worth an explicit test.
- **Cache stampede on cold start** — TTL jitter + `get_or_set`.
