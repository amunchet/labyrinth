#!/bin/sh
# UniFi: refresh controller snapshots, add new devices to the inventory, alert on offline ones
cd /src/
if [ -f .env ]; then
	set -a
	. .env
	set +a
fi
PYTHONPATH=. python3 unifi_helper.py 2>&1
