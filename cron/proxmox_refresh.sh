#!/bin/sh
echo "Starting proxmox_refresh..."
cd /src/
if [ -f .env ]; then
	set -a
	. .env
	set +a
fi
python3 proxmox_refresh.py 2>&1
echo "Done."
