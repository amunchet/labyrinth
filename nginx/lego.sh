#!/bin/bash

while true; do
    echo "Getting certificate..."
    cd  /nginx
    lego -a --email $CLOUDFLARE_EMAIL --dns cloudflare --domains $DOMAIN run


    echo "Sleeping 24 hours..."
    sleep 86400
done
