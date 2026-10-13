#!/bin/bash
echo "Building dist..."

cd /src
npm ci --ignore-scripts


echo "Building..."
npm run build
