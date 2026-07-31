"""
Database adapter ecosystem.

Selects a backend via the `DB_BACKEND` env var (default: "postgres").
`DB_BACKEND=mongo` keeps a full-fidelity MongoDB fallback available (no
functionality lost, no data migration required for existing Mongo
deployments that aren't ready to cut over) - see MONGO_MIGRATION.md.
"""

import os


def get_db():
    """Returns a `db.base.Client` for the configured backend."""
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
