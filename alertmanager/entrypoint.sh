#!/bin/bash

echo "Running pre-start password check..."
python3 /src/installer.py

echo "Starting alertmanager"
/usr/local/bin/alertmanager  --config.file=/src/alertmanager.yml --web.config.file=/src/webconfig.yml --log.level=debug 2>&1
