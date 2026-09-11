#!/bin/sh
# Dump the database to /backups for offsite pickup - see
# backend/backup_db.py and MONGO_MIGRATION.md.

cd /src
if [ -f .env ]; then
	set -a;
	source .env;
	set +a;
fi

PYTHONPATH=. python3 backup_db.py 2>&1

