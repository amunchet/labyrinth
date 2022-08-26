#!/bin/sh
# Entrypoint script for docker
echo "Starting entrypoint.sh..."

echo "Running dos2unix..."
dos2unix /cron/cron.d/crontab

echo "Permissions and installing cron"
chmod 0644 /cron/cron.d/*
crontab /cron/cron.d/crontab
touch /var/log/cron.log

cron -f 2>&1