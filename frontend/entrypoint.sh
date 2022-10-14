#!/bin/bash

# Entrypoint for Frontend Docker
echo 'Installing project...'
cd /src/labyrinth && npm install

echo "Runing npm upgrade..."
cd /src/labyrinth && npm upgrade


if [[ -z "{$TESTBED}" ]]; then
    echo "Building vue app..."
    cd /src/labyrinth/ && npm run build
else
    echo "Starting devel server..."
    # cd /src/ && npm run serve
    cd /src/ && vue ui -D -H 0.0.0.0
fi
