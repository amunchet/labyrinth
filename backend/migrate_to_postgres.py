#!/usr/bin/env python3
"""
One-time, idempotent migration: copies all Labyrinth collections from a live
MongoDB source into Postgres/TimescaleDB. Safe to re-run (upsert-by-id
semantics - re-running after a partial failure, or to pick up documents
added since a prior run, produces the same end state).

Not invoked automatically by the app or by cron - an operator runs this by
hand when ready to cut a deployment over from DB_BACKEND=mongo to
DB_BACKEND=postgres. See MONGO_MIGRATION.md for the full runbook.

This script does NOT touch the MongoDB Atlas scheduled Trigger described in
README.md (a `metrics-latest` -> `metrics` $merge, configured entirely in
Atlas's control plane, invisible to this repo) - if your deployment has one,
disable it in the Atlas console yourself once you've cut over, or it will
keep running forever against an abandoned cluster.

Usage:
    python3 migrate_to_postgres.py [--dry-run] [--verify-only]

Reads connection details from the same env vars the app itself uses
(MONGO_USERNAME/MONGO_PASSWORD/MONGO_HOST, POSTGRES_HOST/PORT/USER/
PASSWORD/DB, GITHUB/TESTBED). `backend/.env` is loaded automatically, the
same way `serve.py` and the `ai/` jobs do it - the production backend
container sets only DB_BACKEND/POSTGRES_*/REDIS_HOST in compose, so the
Mongo credentials this script needs exist *only* in that file. Already
exported variables win over the file's values.
"""

import argparse
import sys

from dotenv import load_dotenv

from db import base
from db.mongo_adapter import MongoClientAdapter
from db.postgres_adapter import PostgresClientAdapter

# Before importing anything that reads the environment at call time, so a
# hand-run migration inside the production container picks up MONGO_* from
# /src/.env instead of building a "mongodb+srv://user:pass@None" URI.
load_dotenv()

# Cheap/small collections first for fast feedback; metrics (potentially
# large, unbounded under current Mongo behavior) last.
COLLECTIONS = [
    "subnets",
    "hosts",
    "services",
    "settings",
    "proxmox_clusters",
    "aws_accounts",
    "themes",
    "dashboards",
    "metrics-latest",
    "metrics",
]

BATCH_SIZE = 5000


def _copy_collection(mongo_db, pg_db, name, dry_run):
    source = mongo_db[name]
    dest = None if dry_run else pg_db[name]

    count = 0
    batch = []
    for doc in source.find({}):
        count += 1
        if dry_run:
            continue
        batch.append(doc)
        if len(batch) >= BATCH_SIZE:
            _write_batch(dest, batch)
            batch = []
    if batch:
        _write_batch(dest, batch)

    return count


def _write_batch(dest, batch):
    dest.bulk_write(
        [base.ReplaceOne({"_id": doc["_id"]}, doc, upsert=True) for doc in batch]
    )


def _verify_counts(mongo_db, pg_db):
    print("\nVerifying per-collection counts (source vs destination):")
    all_match = True
    for name in COLLECTIONS:
        source_count = mongo_db[name].count_documents({})
        dest_count = pg_db[name].count_documents({})
        status = "OK" if source_count == dest_count else "MISMATCH"
        if source_count != dest_count:
            all_match = False
        print(
            "  {:<20} mongo={:<8} postgres={:<8} {}".format(
                name, source_count, dest_count, status
            )
        )
    return all_match


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read from Mongo and print counts only; write nothing to Postgres.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip copying; just compare counts between the two databases.",
    )
    args = parser.parse_args()

    mongo_client = MongoClientAdapter()
    mongo_db = mongo_client["labyrinth"]

    if args.verify_only:
        pg_client = PostgresClientAdapter()
        ok = _verify_counts(mongo_db, pg_client["labyrinth"])
        sys.exit(0 if ok else 1)

    print(
        "{} mode - copying Labyrinth collections from Mongo to Postgres.\n".format(
            "DRY RUN" if args.dry_run else "LIVE"
        )
    )

    pg_client = None if args.dry_run else PostgresClientAdapter()
    pg_db = pg_client["labyrinth"] if pg_client else None

    for name in COLLECTIONS:
        count = _copy_collection(mongo_db, pg_db, name, args.dry_run)
        print(
            "  {:<20} {} documents{}".format(
                name, count, " (not written - dry run)" if args.dry_run else ""
            )
        )

    if args.dry_run:
        print("\nDry run complete. Re-run without --dry-run to write to Postgres.")
        return

    ok = _verify_counts(mongo_db, pg_db)
    if not ok:
        print(
            "\nCount mismatch detected - see above. Re-running this script is "
            "safe (upsert-by-id) and may resolve transient mismatches if "
            "writes were happening during the copy; investigate further if "
            "mismatches persist."
        )
        sys.exit(1)

    print(
        "\nMigration complete and verified. Remember to:\n"
        "  1. Set DB_BACKEND=postgres in backend/.env (and remove/rotate the\n"
        "     Mongo credentials there once you're confident in the cutover).\n"
        "  2. If your MongoDB Atlas cluster has a scheduled Trigger merging\n"
        "     metrics-latest into metrics (see README.md), disable it in the\n"
        "     Atlas console - it isn't managed by this repo or this script.\n"
    )


if __name__ == "__main__":  # pragma: no cover
    main()
