#!/bin/sh

# Entrypoint script for docker
echo "Starting entrypoint.sh..."

echo "Testbed mode"

/src/serve.py

