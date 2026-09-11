"""
Database adapter ecosystem.

Selects a backend via the `DB_BACKEND` env var (default: "postgres").
`DB_BACKEND=mongo` keeps a full-fidelity MongoDB fallback available (no
functionality lost, no data migration required for existing Mongo
deployments that aren't ready to cut over) - see MONGO_MIGRATION.md.

Connection ownership
--------------------
Every `get_db()` call builds a *new* client, and on Postgres a client owns a
`ThreadedConnectionPool`. Nothing reaps those pools, so calling `get_db()`
per request/per job in a long-lived process leaks server connections until
Postgres answers with "sorry, too many clients already".

So there are two entry points, and the distinction matters:

- `get_db()`     - always constructs a fresh client. For tests, one-shot
                   tooling, and anything that genuinely wants its own pool
                   and will `close()` it.
- `shared_db()`  - the process-wide client. Built once on first *use*,
                   reused forever after, closed at interpreter exit.
                   This is what application code wants.

`shared_db()` returns a lazy proxy: importing a module that holds one does
not open a socket. That matters because `serve.py` is imported by half a
dozen short-lived cron entrypoints every minute (finder, bulk_write,
proxmox_refresh, alive, ...), most of which touch few or no tables - an
eager module-level client made every one of them open a pool and run the
schema bootstrap's advisory-lock DDL just to import a helper function.
"""

import atexit
import os
import threading

from db import base


def get_db():
    """Returns a **new** `db.base.Client` for the configured backend.

    The caller owns the returned client and is responsible for `close()`.
    Prefer `shared_db()` in application code - see the module docstring.
    """
    backend = (os.environ.get("DB_BACKEND") or "postgres").strip().lower()
    if backend == "mongo":
        from db.mongo_adapter import MongoClientAdapter

        return MongoClientAdapter()
    if backend == "postgres":
        from db.postgres_adapter import PostgresClientAdapter

        return PostgresClientAdapter()
    raise ValueError(
        "Unknown DB_BACKEND: {!r} (expected 'postgres' or 'mongo')".format(backend)
    )


# --- Process-wide shared client --------------------------------------------

_shared_client = None
_shared_lock = threading.Lock()


def get_shared_client():
    """The one client this process should use, built on first call.

    Thread-safe: gunicorn workers run AI chat turns on background threads,
    so two threads can race here on the very first database touch.
    """
    global _shared_client
    if _shared_client is None:
        with _shared_lock:
            if _shared_client is None:
                _shared_client = get_db()
    return _shared_client


def close_shared_client():
    """Close and forget the shared client, if one was ever built.

    Registered at exit so short-lived cron processes hand their connections
    back promptly instead of leaving Postgres to reap them on socket close.
    Also the reset hook tests need between backend switches.
    """
    global _shared_client
    with _shared_lock:
        client = _shared_client
        _shared_client = None
    if client is not None:
        try:
            client.close()
        except Exception:  # pragma: no cover - teardown must never raise
            pass


atexit.register(close_shared_client)


class _LazyClient(base.Client):
    """Proxy that resolves to the shared client on first actual use.

    Deliberately not a `__getattr__` catch-all: the `Client` contract is
    three methods wide, and an explicit surface keeps a typo from silently
    constructing a pool.
    """

    def __getitem__(self, database_name):
        return get_shared_client()[database_name]

    def close(self):
        close_shared_client()

    def get_pool(self):
        """Postgres-only escape hatch (compaction, backups)."""
        return get_shared_client().get_pool()

    @property
    def resolved(self):
        """The underlying client, or None if nothing has touched it yet.

        Lets tests and diagnostics ask "did this process ever connect?"
        without being the thing that makes it connect.
        """
        return _shared_client


def shared_db():
    """Returns a lazy proxy onto the process-wide client."""
    return _LazyClient()
