#!/bin/sh

# Entrypoint script for docker
echo "Starting SSH agent..."
eval `ssh-agent`

echo "Starting entrypoint.sh..."

if [ -z "$PRODUCTION"]; then
	echo "Testbed mode"
	/src/serve.py 2>&1
else
	echo "Starting production..."
	cd /src
	# --timeout: the default 30s killed workers mid-request on the slower
	# routes (Proxmox/AWS fan-out, bulk writes). Agent chat turns no longer
	# run inline, but keep headroom so a slow upstream isn't a worker kill.
	gunicorn --bind 0.0.0.0:7000 --workers 8 --timeout "${GUNICORN_TIMEOUT:-120}" serve:app
fi
