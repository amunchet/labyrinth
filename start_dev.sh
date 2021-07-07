#!/bin/sh
echo "Starting development docker..."
docker-compose -f docker-compose-development.yml up --build -d