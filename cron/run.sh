#!/bin/sh
echo "Starting finder..."
cd /src/ 
MONGO_HOST=mongo REDIS_HOST=redis MONGO_USERNAME=root MONGO_PASSWORD=temp python3 finder.py 2>&1 
echo "Done."
