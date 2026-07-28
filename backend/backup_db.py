#!/usr/bin/env python3
"""
Dumps the Postgres/TimescaleDB database to a timestamped pg_dump custom-
format file under /backups. An external system (not this script's concern -
see MONGO_MIGRATION.md) is expected to pick files up from there for offsite
storage; this script only keeps BACKUP_RETENTION_DAYS of local history so
/backups itself doesn't grow unboundedly.

Postgres-only (no-ops cleanly under DB_BACKEND=mongo). Intended to run daily
via cron/backup_db.sh, after cron/compact_metrics.sh so backups capture the
already-compacted, smaller data.

Prints a final "BACKUP OK: ..." or "BACKUP FAILED: ..." line and exits
non-zero on failure, so a failed backup is greppable/alertable rather than
silently lost in cron output.
"""

import datetime
import os
import subprocess
import sys

BACKUP_DIR = "/backups"


def _env(name, default=None):
    return os.environ.get(name, default)


def _backup_retention_days():
    value = (_env("BACKUP_RETENTION_DAYS") or "14").strip()
    return int(value) if value else 14


def _dump_filename():
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "labyrinth-{}-{}.dump".format(_env("POSTGRES_DB", "labyrinth"), timestamp)


def _prune_old_backups():
    retention_days = _backup_retention_days()
    cutoff = datetime.datetime.now().timestamp() - retention_days * 86400
    pruned = 0
    for name in os.listdir(BACKUP_DIR):
        if not name.startswith("labyrinth-") or not name.endswith(".dump"):
            continue
        path = os.path.join(BACKUP_DIR, name)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)
            pruned += 1
    if pruned:
        print(
            "Pruned {} local backup(s) older than {} days.".format(
                pruned, retention_days
            )
        )


def backup_db():
    backend = (_env("DB_BACKEND") or "postgres").strip().lower()
    if backend != "postgres":
        print(
            "DB_BACKEND={!r} (not postgres) - skipping database backup.".format(backend)
        )
        return 0

    os.makedirs(BACKUP_DIR, exist_ok=True)

    dump_path = os.path.join(BACKUP_DIR, _dump_filename())
    env = dict(os.environ)
    env["PGPASSWORD"] = _env("POSTGRES_PASSWORD", "")

    pg_dump_cmd = [
        "pg_dump",
        "--host",
        _env("POSTGRES_HOST", "postgres"),
        "--port",
        _env("POSTGRES_PORT", "5432"),
        "--username",
        _env("POSTGRES_USER", "labyrinth"),
        "--format=custom",
        "--file",
        dump_path,
        _env("POSTGRES_DB", "labyrinth"),
    ]

    try:
        subprocess.run(pg_dump_cmd, env=env, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        print(
            "BACKUP FAILED: pg_dump exited {}: {}".format(
                exc.returncode, exc.stderr.strip()
            )
        )
        return 1
    except FileNotFoundError:
        print("BACKUP FAILED: pg_dump not found (postgresql-client not installed?)")
        return 1

    if not os.path.exists(dump_path) or os.path.getsize(dump_path) == 0:
        print("BACKUP FAILED: dump file missing or empty: {}".format(dump_path))
        return 1

    try:
        subprocess.run(
            ["pg_restore", "--list", dump_path],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            "BACKUP FAILED: dump failed pg_restore --list sanity check: {}".format(
                exc.stderr.strip()
            )
        )
        return 1

    size_kb = os.path.getsize(dump_path) // 1024
    print("BACKUP OK: {} ({} KB)".format(dump_path, size_kb))

    _prune_old_backups()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(backup_db())
