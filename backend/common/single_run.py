"""
Cross-container "only one of these at a time" lock, with waiting.

`pid.PidFile` (used elsewhere in this repo) does neither of the two things
the Redis->Postgres metrics transfer needs:

1. It is per-container. Redis and Postgres are shared, so two cron
   containers would each happily run their own "single" transfer and
   double-write the same metrics. finder.py already reaches for a Redis
   lock for exactly this reason.
2. It aborts on contention instead of waiting. The transfer is scheduled
   every minute; when a run spills past the minute mark we want the next
   tick to *queue behind it*, not to give up and drop that window's data.

So: a Redis lock with a fencing token, a blocking acquire, and a heartbeat
that extends the TTL for as long as the holder is alive.

The TTL is what makes this safe against a hard crash - a holder that dies
(OOM, SIGKILL, container restart) stops heartbeating and the lock frees
itself within `ttl` seconds rather than wedging the transfer forever.
"""

import contextlib
import os
import threading
import time
import uuid

# Long enough that a normal transfer never races its own expiry even if the
# heartbeat thread is starved; short enough that a crashed holder frees the
# lock within a couple of cron ticks.
DEFAULT_TTL_SECONDS = 120

# How long a waiter blocks before giving up. Cron re-fires every minute, so
# giving up is not data loss - Redis still holds the metrics (120s TTL) and
# the next tick retries. Capping the wait is what stops a permanently stuck
# holder from accumulating an unbounded pile of blocked cron processes.
DEFAULT_WAIT_SECONDS = 240

DEFAULT_POLL_SECONDS = 1.0

# Release only if we still own the lock. Without the token check, a holder
# that overran its TTL would delete the *next* holder's lock on the way out.
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

_EXTEND_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('pexpire', KEYS[1], ARGV[2])
else
    return 0
end
"""


class LockNotAcquired(Exception):
    """Raised when the wait budget ran out before the lock came free."""


class RedisSingleRunLock:
    """A mutually-exclusive, self-expiring, heartbeat-extended Redis lock."""

    def __init__(
        self,
        redis_client,
        key,
        ttl=DEFAULT_TTL_SECONDS,
        wait=DEFAULT_WAIT_SECONDS,
        poll_interval=DEFAULT_POLL_SECONDS,
    ):
        self._redis = redis_client
        self._key = key
        self._ttl = float(ttl)
        self._wait = float(wait)
        self._poll = float(poll_interval)
        self._token = uuid.uuid4().hex
        self._heartbeat = None
        self._stop = threading.Event()
        self.waited_seconds = 0.0

    # -- acquire / release ------------------------------------------------

    def acquire(self):
        """Block until the lock is ours, or raise LockNotAcquired."""
        deadline = time.monotonic() + self._wait
        started = time.monotonic()

        while True:
            if self._redis.set(
                self._key, self._token, nx=True, px=int(self._ttl * 1000)
            ):
                self.waited_seconds = time.monotonic() - started
                self._start_heartbeat()
                return True

            if time.monotonic() >= deadline:
                self.waited_seconds = time.monotonic() - started
                raise LockNotAcquired(
                    "{!r} still held after waiting {:.1f}s".format(
                        self._key, self.waited_seconds
                    )
                )

            # Sleep no further than the deadline so `wait` is honored even
            # when it is not a whole multiple of the poll interval.
            time.sleep(min(self._poll, max(0.0, deadline - time.monotonic())))

    def release(self):
        self._stop.set()
        if self._heartbeat is not None:
            self._heartbeat.join(timeout=self._poll * 2)
            self._heartbeat = None
        try:
            self._redis.eval(_RELEASE_LUA, 1, self._key, self._token)
        except Exception:  # pragma: no cover - releasing must never mask work
            pass

    # -- heartbeat --------------------------------------------------------

    def _start_heartbeat(self):
        self._stop.clear()
        # Daemon: a stuck heartbeat must never keep a cron process alive.
        self._heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            name="single-run-heartbeat",
            daemon=True,
        )
        self._heartbeat.start()

    def _heartbeat_loop(self):
        interval = max(self._ttl / 3.0, 1.0)
        while not self._stop.wait(interval):
            try:
                self._redis.eval(
                    _EXTEND_LUA, 1, self._key, self._token, int(self._ttl * 1000)
                )
            except Exception:  # pragma: no cover - transient Redis blip
                # Keep trying; the TTL still protects us if Redis stays down.
                pass

    # -- context manager --------------------------------------------------

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
        return False


def _env_float(name, default):
    try:
        value = float(os.environ.get(name) or default)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


@contextlib.contextmanager
def single_run(redis_client, key, ttl=None, wait=None, poll_interval=None):
    """Run the body under `key`, waiting for any in-flight run to finish.

    Tunable per lock via `<KEY>_LOCK_TTL_SECONDS` / `_LOCK_WAIT_SECONDS`
    env vars, where `<KEY>` is the upper-cased key with dashes as
    underscores (e.g. `BULK_INSERT_LOCK_WAIT_SECONDS`).
    """
    prefix = key.replace("-", "_").upper()
    lock = RedisSingleRunLock(
        redis_client,
        key,
        ttl=(
            ttl
            if ttl is not None
            else _env_float(prefix + "_LOCK_TTL_SECONDS", DEFAULT_TTL_SECONDS)
        ),
        wait=(
            wait
            if wait is not None
            else _env_float(prefix + "_LOCK_WAIT_SECONDS", DEFAULT_WAIT_SECONDS)
        ),
        poll_interval=(
            poll_interval
            if poll_interval is not None
            else _env_float(prefix + "_LOCK_POLL_SECONDS", DEFAULT_POLL_SECONDS)
        ),
    )
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()
