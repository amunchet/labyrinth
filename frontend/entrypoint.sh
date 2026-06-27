#!/bin/bash
set -euo pipefail

echo 'Installing project...'
cd /src/labyrinth && npm install


# Avoid runtime mass upgrades that break compatibility
# echo "Running npm upgrade..."  # (intentionally disabled)

if [[ -z "${TESTBED:-}" ]]; then
  echo "Deleting dist..."
  rm -rf dist

  echo "Building vue app..."
  npm run build

  echo "Moving from /var/tmp/labyrinth/dist..."
  mkdir -p /src/labyrinth/dist
  # package.json writes to /var/tmp/labyrinth/dist via vue.outputDir
  mv /var/tmp/labyrinth/dist/* /src/labyrinth/dist
else
  echo "Starting Vue UI (dev) ..."
  cd /src/labyrinth
  # vue ui serves on 0.0.0.0:8000 by default
  # vue ui -D -H 0.0.0.0
  npm run serve
fi
