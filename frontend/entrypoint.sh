#!/bin/bash

# Entrypoint for Frontend Docker
echo 'Installing project...'
cd /src/labyrinth && npm install

echo "Runing npm upgrade..."
cd /src/labyrinth && npm upgrade


if [[ -z "$TESTBED" ]]; then
    echo "Deleting dist..."
    cd /src/labyrinth && rm -rf dist
    echo "Building vue app..."
    cd /src/labyrinth/ && npm run build
    echo "Moving from /tmp/dist..."
    mkdir /src/labyrinth/dist || true
    mv /tmp/dist/* /src/labyrinth/dist
else
    echo "Starting devel server..."
    # cd /src/ && npm run serve
    cd /src/ && vue ui -D -H 0.0.0.0
fi
