#!/bin/sh
# Compact metrics rows older than METRICS_RAW_RETENTION_DAYS into
# metrics_daily - see backend/compact_metrics.py and MONGO_MIGRATION.md.

cd /src
if [ -f .env ]; then
	set -a;
	source .env;
	set +a;
fi

PYTHONPATH=. python3 compact_metrics.py 2>&1

