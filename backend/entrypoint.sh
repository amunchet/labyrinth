#!/bin/sh

# Entrypoint script for docker
echo "Starting entrypoint.sh..."

if [ -z "$PRODUCTION"]; then
	echo "Testbed mode"
	/src/serve.py
else
	echo "Starting production..."
	cd /src
	gunicorn --bind 0.0.0.0:7000 --workers 4 serve:app
fi
