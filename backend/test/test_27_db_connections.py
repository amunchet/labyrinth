#!/usr/bin/env python3
"""
Connection-lifecycle tests for backend/db/.

These cover the ways the stack ran Postgres out of connections
("FATAL: sorry, too many clients already"):

  - a client built per call instead of once per process
  - a client built eagerly at import, in cron processes that then exit
  - a pooled connection stranded when a query raised

Assertions are against `pg_stat_activity` through an independent observer
connection, so they measure real server-side backends rather than the
pool's own bookkeeping.
"""

import os
import threading

import psycopg2
import psycopg2.pool
import pytest

import db as db_pkg
from db import postgres_adapter
from db.postgres_adapter import PostgresClientAdapter, _pool_bounds

pytestmark = pytest.mark.skipif(
    (os.environ.get("DB_BACKEND") or "postgres").strip().lower() != "postgres",
    reason="Postgres connection semantics only apply to the Postgres backend",
)


def _dsn():
    return "host={} port={} user={} password={} dbname={}".format(
        os.environ.get("POSTGRES_HOST", "postgres"),
        os.environ.get("POSTGRES_PORT", "5432"),
        os.environ.get("POSTGRES_USER", "labyrinth"),
        os.environ.get("POSTGRES_PASSWORD", ""),
        os.environ.get("POSTGRES_DB", "labyrinth"),
    )


@pytest.fixture
def observer():
    conn = psycopg2.connect(_dsn())
    conn.autocommit = True
    yield conn
    conn.close()


def backend_count(observer):
    """Server-side connections to our database, excluding the observer."""
    with observer.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            [os.environ.get("POSTGRES_DB", "labyrinth")],
        )
        return cur.fetchone()[0]


# --- shared client ----------------------------------------------------------


def test_shared_client_is_reused_across_calls():
    db_pkg.close_shared_client()
    try:
        first = db_pkg.get_shared_client()
        assert db_pkg.get_shared_client() is first
        assert db_pkg.get_shared_client() is first
    finally:
        db_pkg.close_shared_client()


def test_repeated_shared_client_use_does_not_grow_connections(observer):
    """The regression that caused "too many clients": a pool per call."""
    db_pkg.close_shared_client()
    try:
        db_pkg.get_shared_client()["labyrinth"]["settings"].find_one({"name": "x"})
        settled = backend_count(observer)

        for _ in range(30):
            db_pkg.get_shared_client()["labyrinth"]["settings"].find_one({"name": "x"})

        assert backend_count(observer) == settled
    finally:
        db_pkg.close_shared_client()


def test_close_shared_client_releases_connections(observer):
    db_pkg.close_shared_client()
    before = backend_count(observer)

    db_pkg.get_shared_client()["labyrinth"]["settings"].find_one({"name": "x"})
    assert backend_count(observer) > before

    db_pkg.close_shared_client()
    assert backend_count(observer) == before


def test_close_shared_client_is_idempotent():
    db_pkg.close_shared_client()
    db_pkg.close_shared_client()  # must not raise on a never-built client


def test_concurrent_first_use_builds_exactly_one_client():
    """Gunicorn workers run AI chat on background threads, so two threads
    can reach the very first database touch at the same time. The
    double-checked lock must yield one client, not two pools."""
    db_pkg.close_shared_client()
    try:
        clients = []
        barrier = threading.Barrier(8)

        def race():
            barrier.wait()
            clients.append(db_pkg.get_shared_client())

        threads = [threading.Thread(target=race) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert len(clients) == 8
        assert all(client is clients[0] for client in clients)
    finally:
        db_pkg.close_shared_client()


def test_loser_of_the_construction_race_reuses_the_winners_client():
    """The inner half of the double-checked lock: a thread that blocks on
    the lock must return what the winner built, not build its own."""
    db_pkg.close_shared_client()
    try:
        winner = object()
        real_lock = db_pkg._shared_lock

        class LockThatLosesTheRace:
            """Stands in for 'another thread won while we waited here'."""

            def __enter__(self):
                real_lock.acquire()
                db_pkg._shared_client = winner
                return self

            def __exit__(self, *exc):
                real_lock.release()
                return False

        db_pkg._shared_lock = LockThatLosesTheRace()
        try:
            assert db_pkg.get_shared_client() is winner
        finally:
            db_pkg._shared_lock = real_lock
    finally:
        db_pkg._shared_client = None


# --- lazy proxy -------------------------------------------------------------


def test_shared_db_proxy_does_not_connect_until_used(observer):
    """Cron entrypoints `import serve` just to reuse helpers, then exit."""
    db_pkg.close_shared_client()
    try:
        before = backend_count(observer)

        proxy = db_pkg.shared_db()
        assert proxy.resolved is None
        assert backend_count(observer) == before, "building the proxy connected"

        proxy["labyrinth"]["settings"].find_one({"name": "x"})
        assert proxy.resolved is not None
        assert backend_count(observer) > before
    finally:
        db_pkg.close_shared_client()


def test_shared_db_proxy_resolves_to_the_shared_client():
    db_pkg.close_shared_client()
    try:
        proxy = db_pkg.shared_db()
        proxy["labyrinth"]["settings"].find_one({"name": "x"})
        assert proxy.resolved is db_pkg.get_shared_client()
    finally:
        db_pkg.close_shared_client()


def test_serve_module_db_is_lazy():
    """serve.py is imported by finder/alive/updater - it must not connect."""
    import serve

    assert isinstance(serve.db, db_pkg._LazyClient)


# --- pool cursor leak -------------------------------------------------------


def _kill_idle_pooled_connections(pool):
    """Make every idle connection in the pool dead, as a Postgres restart would.

    Closed client-side rather than via pg_terminate_backend because that is
    what psycopg2 sees either way, and it keeps the test independent of how
    quickly libpq notices a server-side termination.
    """
    for conn in list(pool._pool):
        conn.close()


def test_dead_pooled_connection_does_not_leak_a_pool_slot():
    """The Postgres-restart path: setup failure used to strand the connection.

    `conn.autocommit = True` raises InterfaceError on a dead connection. If
    that escapes before the connection is returned, the pool slot is gone
    for good - `maxconn` of those and the process can never reach Postgres
    again without a restart.
    """
    client = PostgresClientAdapter()
    try:
        pool = client.get_pool()
        _, maxconn = _pool_bounds()

        # Far more iterations than the pool has slots: if any one of them
        # strands its connection, the pool is exhausted well before the end.
        for _ in range(maxconn * 5):
            _kill_idle_pooled_connections(pool)
            try:
                with postgres_adapter._cursor(pool) as cur:
                    cur.execute("SELECT 1")
            except psycopg2.InterfaceError:
                # Expected for the dead connection itself - what must NOT
                # happen is the slot disappearing along with it.
                pass
            assert len(pool._used) == 0, "connection was never returned to the pool"

        # And the pool is still usable afterwards.
        with postgres_adapter._cursor(pool) as cur:
            cur.execute("SELECT 1 AS ok")
            assert cur.fetchone()["ok"] == 1
    finally:
        client.close()


def test_dead_pooled_connection_does_not_leak_server_backends(observer):
    client = PostgresClientAdapter()
    try:
        pool = client.get_pool()
        _, maxconn = _pool_bounds()

        with postgres_adapter._cursor(pool) as cur:
            cur.execute("SELECT 1")
        settled = backend_count(observer)

        for _ in range(maxconn * 5):
            _kill_idle_pooled_connections(pool)
            try:
                with postgres_adapter._cursor(pool) as cur:
                    cur.execute("SELECT 1")
            except psycopg2.InterfaceError:
                pass

        assert backend_count(observer) <= settled
    finally:
        client.close()


def test_failed_query_returns_its_connection_to_the_pool():
    """An ordinary query error must not cost a pool slot either."""
    client = PostgresClientAdapter()
    try:
        pool = client.get_pool()
        _, maxconn = _pool_bounds()

        for _ in range(maxconn * 5):
            with pytest.raises(psycopg2.Error):
                with postgres_adapter._cursor(pool) as cur:
                    cur.execute("SELECT * FROM a_table_that_does_not_exist")
            assert len(pool._used) == 0

        with postgres_adapter._cursor(pool) as cur:
            cur.execute("SELECT 1 AS ok")
            assert cur.fetchone()["ok"] == 1
    finally:
        client.close()


# --- pool sizing ------------------------------------------------------------


def test_pool_bounds_default_is_small(monkeypatch):
    """Budget: 13ish processes against the timescale image's max_connections=50."""
    monkeypatch.delenv("POSTGRES_POOL_MIN", raising=False)
    monkeypatch.delenv("POSTGRES_POOL_MAX", raising=False)
    minconn, maxconn = _pool_bounds()
    assert minconn == 1
    assert maxconn == 2


def test_pool_bounds_are_configurable(monkeypatch):
    monkeypatch.setenv("POSTGRES_POOL_MIN", "2")
    monkeypatch.setenv("POSTGRES_POOL_MAX", "9")
    assert _pool_bounds() == (2, 9)


def test_pool_bounds_reject_nonsense(monkeypatch):
    monkeypatch.setenv("POSTGRES_POOL_MIN", "not-a-number")
    monkeypatch.setenv("POSTGRES_POOL_MAX", "0")
    minconn, maxconn = _pool_bounds()
    assert minconn == 1
    # max is clamped up to min rather than left at an unusable 0
    assert maxconn >= minconn


def test_connect_with_retry_honors_explicit_bounds(monkeypatch):
    """Callers passing bounds explicitly must not be overridden by env."""
    monkeypatch.setenv("POSTGRES_POOL_MIN", "1")
    monkeypatch.setenv("POSTGRES_POOL_MAX", "2")
    pool = postgres_adapter._connect_with_retry(
        postgres_adapter._connection_dsn(), minconn=1, maxconn=4
    )
    try:
        assert pool.maxconn == 4
    finally:
        pool.closeall()


def test_pool_respects_configured_max(monkeypatch, observer):
    monkeypatch.setenv("POSTGRES_POOL_MIN", "1")
    monkeypatch.setenv("POSTGRES_POOL_MAX", "3")
    client = PostgresClientAdapter()
    try:
        pool = client.get_pool()
        conns = [pool.getconn() for _ in range(3)]
        try:
            with pytest.raises(psycopg2.pool.PoolError):
                pool.getconn()
        finally:
            for conn in conns:
                pool.putconn(conn)
    finally:
        client.close()
