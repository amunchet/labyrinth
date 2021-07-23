#!/bin/sh

# Entrypoint for Frontend Docker
echo 'Installing project...'
cd /src/labyrinth && npm install

echo "Runing npm upgrade..."
cd /src/labyrinth && npm upgrade

echo "Starting..."
# cd /src/ && npm run serve
cd /src/ && vue ui -D -H 0.0.0.0
