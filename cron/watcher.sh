#!/bin/sh
cd /src 
MONGO_HOST=mongo REDIS_HOST=redis MONGO_USERNAME=root MONGO_PASSWORD=temp python3 serve.py watcher 2>&1 