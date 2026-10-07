#!/usr/bin/env python3
"""
Tests for the cross-container single-run lock (common/single_run.py) that
serialises the Redis->Postgres metrics transfer.

Runs against the real Redis this suite already depends on, since the lock's
whole contract is Redis semantics (SET NX PX, Lua compare-and-delete).
"""

import os
import threading
import time
import uuid

import pytest
import redis

from common.single_run import (
    DEFAULT_TTL_SECONDS,
    DEFAULT_WAIT_SECONDS,
    LockNotAcquired,
    RedisSingleRunLock,
    single_run,
)


@pytest.fixture
def rc():
    client = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
    yield client


@pytest.fixture
def key(rc):
    name = "test-single-run-{}".format(uuid.uuid4().hex)
    yield name
    rc.delete(name)


# --- mutual exclusion -------------------------------------------------------


def test_second_acquire_is_blocked_while_first_is_held(rc, key):
    first = RedisSingleRunLock(rc, key, ttl=30, wait=0.5, poll_interval=0.05)
    first.acquire()
    try:
        second = RedisSingleRunLock(rc, key, ttl=30, wait=0.5, poll_interval=0.05)
        with pytest.raises(LockNotAcquired):
            second.acquire()
    finally:
        first.release()


def test_lock_is_reacquirable_after_release(rc, key):
    with single_run(rc, key, ttl=30, wait=1):
        pass
    # Released, so a second run gets it immediately.
    with single_run(rc, key, ttl=30, wait=1) as lock:
        assert lock.waited_seconds < 1


def test_waiter_blocks_until_holder_finishes_then_proceeds(rc, key):
    """The overrun case: a slow transfer must hold the next tick back."""
    holder = RedisSingleRunLock(rc, key, ttl=30, wait=0.1, poll_interval=0.05)
    holder.acquire()

    order = []

    def waiter():
        lock = RedisSingleRunLock(rc, key, ttl=30, wait=10, poll_interval=0.05)
        lock.acquire()
        order.append("waiter-acquired")
        lock.release()

    thread = threading.Thread(target=waiter)
    thread.start()

    # Give the waiter time to prove it is actually blocked, not just slow.
    time.sleep(0.5)
    assert order == [], "waiter ran while the lock was held"

    order.append("holder-released")
    holder.release()

    thread.join(timeout=10)
    assert not thread.is_alive()
    assert order == ["holder-released", "waiter-acquired"]


def test_waiter_reports_how_long_it_waited(rc, key):
    holder = RedisSingleRunLock(rc, key, ttl=30, wait=0.1, poll_interval=0.05)
    holder.acquire()

    def release_soon():
        time.sleep(0.4)
        holder.release()

    threading.Thread(target=release_soon).start()

    lock = RedisSingleRunLock(rc, key, ttl=30, wait=10, poll_interval=0.05)
    lock.acquire()
    try:
        assert lock.waited_seconds >= 0.3
    finally:
        lock.release()


# --- crash safety -----------------------------------------------------------


def test_lock_expires_if_holder_never_releases(rc, key):
    """A holder that is SIGKILLed must not wedge the transfer forever."""
    # No release, no heartbeat extension past the TTL.
    abandoned = RedisSingleRunLock(rc, key, ttl=1, wait=0.1, poll_interval=0.05)
    abandoned.acquire()
    abandoned._stop.set()  # simulate the process dying: heartbeat stops

    lock = RedisSingleRunLock(rc, key, ttl=5, wait=5, poll_interval=0.1)
    lock.acquire()
    try:
        assert lock.waited_seconds >= 0.5
    finally:
        lock.release()


def test_heartbeat_keeps_lock_alive_past_its_ttl(rc, key):
    """A long transfer must not lose its lock mid-run and let a peer in."""
    lock = RedisSingleRunLock(rc, key, ttl=1.5, wait=0.1, poll_interval=0.05)
    lock.acquire()
    try:
        # Well past the 1.5s TTL - only the heartbeat can keep this alive.
        time.sleep(3)
        assert rc.get(key) == lock._token.encode()

        peer = RedisSingleRunLock(rc, key, ttl=5, wait=0.2, poll_interval=0.05)
        with pytest.raises(LockNotAcquired):
            peer.acquire()
    finally:
        lock.release()
    assert rc.get(key) is None


def test_release_does_not_delete_a_peers_lock(rc, key):
    """Fencing token: an overrun holder must not free the next holder's lock."""
    stale = RedisSingleRunLock(rc, key, ttl=30, wait=0.1)
    stale.acquire()
    stale._stop.set()

    # Peer takes over after the stale holder's key is manually expired.
    rc.delete(key)
    peer = RedisSingleRunLock(rc, key, ttl=30, wait=1, poll_interval=0.05)
    peer.acquire()

    stale.release()  # must be a no-op against the peer's token

    assert rc.get(key) == peer._token.encode()
    peer.release()


# --- context manager / config ----------------------------------------------


def test_single_run_releases_on_exception(rc, key):
    with pytest.raises(RuntimeError):
        with single_run(rc, key, ttl=30, wait=1):
            raise RuntimeError("boom")
    assert rc.get(key) is None


def test_single_run_reads_tunables_from_env(rc, key, monkeypatch):
    prefix = key.replace("-", "_").upper()
    monkeypatch.setenv(prefix + "_LOCK_TTL_SECONDS", "42")
    monkeypatch.setenv(prefix + "_LOCK_WAIT_SECONDS", "7")
    with single_run(rc, key) as lock:
        assert lock._ttl == 42
        assert lock._wait == 7


def test_single_run_ignores_junk_env_values(rc, key, monkeypatch):
    prefix = key.replace("-", "_").upper()
    monkeypatch.setenv(prefix + "_LOCK_TTL_SECONDS", "not-a-number")
    monkeypatch.setenv(prefix + "_LOCK_WAIT_SECONDS", "-5")
    with single_run(rc, key) as lock:
        assert lock._ttl == DEFAULT_TTL_SECONDS
        assert lock._wait == DEFAULT_WAIT_SECONDS
