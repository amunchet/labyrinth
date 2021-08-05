#!/bin/bash

if [[ $EUID -ne 0 ]]; then
	echo "This script must be run as root" 
	exit 1
fi

# Publishes changes
cd labyrinth
echo "Starting build docker..."
docker-compose up --build -d 
cd ..
echo "Done."
