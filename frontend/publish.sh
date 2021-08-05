#!/bin/bash

# Publishes changes

DOCKER_DEVEL_NAME="labyrinth_devel"


echo "Removing dist file..."
rm -rf frontend/labyrinth/dist

echo "Building docker..."
#docker-compose -f docker-compose-development.yml build --no-cache devel 
docker-compose -f docker-compose-development.yml up -d devel

echo "Building project..."

docker exec $DOCKER_DEVEL_NAME sh -c "cd /src/labyrinth && rm -rf package-lock.json && rm -rf node_modules && npm install && echo 'Starting install...' && node_modules/*vue/cli-service/bin/vue-cli-service.js build"

echo "Removing dev docker"
docker stop $DOCKER_DEVEL_NAME && docker rm $DOCKER_DEVEL_NAME


