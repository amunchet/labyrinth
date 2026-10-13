#!/bin/bash
set -euo pipefail

echo 'Installing project...'
# Exactly the lockfile, with dependency install scripts off; canvas is the one
# package that needs its script (it fetches the native binary jsdom loads in the
# unit tests)
cd /src/labyrinth && npm ci --ignore-scripts && npm rebuild canvas


# Avoid runtime mass upgrades that break compatibility
# echo "Running npm upgrade..."  # (intentionally disabled)

if [[ -z "${TESTBED:-}" ]]; then
  echo "Deleting dist..."
  rm -rf dist

  echo "Building vue app..."
  npm run build

  echo "Moving from /tmp/dist..."
  mkdir -p /src/labyrinth/dist
  # package.json writes to /tmp/dist via vue.outputDir
  mv /tmp/dist/* /src/labyrinth/dist
else
  echo "Starting Vue UI (dev) ..."
  cd /src/labyrinth
  # vue ui serves on 0.0.0.0:8000 by default
  # vue ui -D -H 0.0.0.0
  npm run serve
fi

