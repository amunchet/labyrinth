#!/bin/sh
# Proxmox disk space check and alert

cd /src 
if [ -f .env ]; then
	set -a;
	source .env;
	set +a;
fi

PYTHONPATH=. python3 proxmox_disk_check.py 2>&1 

