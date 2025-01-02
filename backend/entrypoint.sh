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
	gunicorn --bind 0.0.0.0:7000 --worker-class gevent --workers 8 -t 600 serve:app 
fi
