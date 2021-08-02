#!/bin/sh

# TODO: Need to start the CVE docker stack as well

echo "Starting development docker..."
docker-compose -f docker-compose-development.yml up --build -d