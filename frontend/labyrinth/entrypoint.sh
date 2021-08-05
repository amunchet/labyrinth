#!/bin/bash
echo "Building dist..."
npm install -g @vue/cli

cd /src
npm install


echo "Building..."
npm run build
