#!/bin/sh

# Watches for directory changes and reloads nginx


while true; do
    echo "Spawning refresh..."
    nginx -t
    if [ $? -eq 0 ]; then
        echo "Reloading Nginx Configuration"
        service nginx reload
    fi
    echo "Done.  Sleeping..."
    sleep 86400
done