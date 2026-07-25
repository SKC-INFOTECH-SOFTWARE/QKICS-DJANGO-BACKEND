"""
Redis-backed idempotency guards and distributed locks.

Built on Django's cache framework (RedisCache in prod, LocMemCache in dev), so
these honour ``CACHE_ENABLED`` and need no separate Redis client. ``cache.add()``
is an atomic SET-if-absent (SETNX) on both backends — it returns True only when
the key did not already exist.

Design rules (keep these true):
  * A lock only *dedupes idempotent work* — it is never the source of truth.
    The real correctness guard is always the DB state (payment status, recording
    status, ...). If Redis is unavailable these helpers FAIL OPEN so an outage
    can never block legitimate processing; the caller's state guard is the
    backstop against the duplicate that then slips through.
  * Never hold money/state in a lock. They gate *repeat execution* only.
"""
import contextlib
import logging
import uuid

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_PREFIX = "lock:"


def _enabled():
    return getattr(settings, "CACHE_ENABLED", True)


def claim_once(key, ttl):
    """
    Idempotency marker. Returns True the FIRST call for ``key`` within ``ttl``
    seconds, False for every call after (until the marker expires).

    Use to make a webhook/callback run its side effects exactly once::

        if not claim_once(f"payu:fulfil:{payment.uuid}", ttl=600):
            return  # a concurrent/duplicate delivery already handled it

    Fails OPEN (returns True) on any cache error so a Redis outage never blocks
    processing — the caller's own state guard is the backstop.
    """
    if not _enabled():
        return True
    try:
        return bool(cache.add(f"{_PREFIX}{key}", "1", ttl))
    except Exception as e:  # Redis down / misconfigured — do not block the caller
        logger.warning("claim_once(%s) cache error, failing open: %s", key, e)
        return True


@contextlib.contextmanager
def distributed_lock(key, ttl=30):
    """
    Best-effort mutual exclusion across processes/workers. Yields True when the
    lock was acquired, False otherwise::

        with distributed_lock(f"egress:upload:{egress_id}", ttl=900) as got:
            if not got:
                return  # another worker is already doing this
            ...work...

    The lock auto-expires after ``ttl`` so a crashed holder cannot wedge it
    forever — pick a ``ttl`` comfortably larger than the protected work. A
    unique token guards release so we never delete a lock that has since expired
    and been re-acquired by someone else. Fails OPEN on cache errors.
    """
    if not _enabled():
        yield True
        return

    lock_key = f"{_PREFIX}{key}"
    token = uuid.uuid4().hex
    try:
        acquired = bool(cache.add(lock_key, token, ttl))
    except Exception as e:
        logger.warning("distributed_lock(%s) acquire error, failing open: %s", key, e)
        yield True
        return

    try:
        yield acquired
    finally:
        if acquired:
            try:
                if cache.get(lock_key) == token:  # still ours — don't drop a re-acquired lock
                    cache.delete(lock_key)
            except Exception as e:
                logger.warning("distributed_lock(%s) release error: %s", key, e)
