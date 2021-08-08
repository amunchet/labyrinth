#!/bin/sh

# TODO: Need to start the CVE docker stack as well

# Need to create the SSL certs if they don't exist...

echo "Touching nginx/.env..."
touch nginx/.env || true

echo "Creating Development SSL..."
LEGODIR="nginx/.lego"
mkdir $LEGODIR || true

DOMAINNAME="development"
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -subj "/C=US/ST=IL/L=Chicago/O=Development/CN=Common" -keyout $LEGODIR/certificates/$DOMAINNAME.key -out $LEGODIR/certificates/$DOMAINNAME.crt

if [ -z "${GITHUB}" ]; then
    echo "[CI] Starting only CI dockers..."
    docker-compose -f docker-compose-development.yml up --build -d frontend
else
    echo "Starting development docker..."
    docker-compose -f docker-compose-development.yml up --build -d
fi
