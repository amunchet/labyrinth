#!/bin/sh
echo "Starting finder..."
cd /src/ 
if [ -f .env ]; then
	set -a;
	source .env;
	set +a;
fi
# MONGO_HOST=mongo REDIS_HOST=redis MONGO_USERNAME=root MONGO_PASSWORD=temp python3 finder.py 2>&1 
python3 finder.py 2>&1 
echo "Done."
