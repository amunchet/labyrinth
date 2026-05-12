#!/bin/bash

# TODO: Remove if docker user is not root
if [[ $EUID -ne 0 ]]; then
echo "This script must be run as root.  If your user is not root but has docker permissions, delete this section from install.sh"
exit 1
fi

echo "Starting production installation."

echo "Initializing submodules..."
git submodule init
git submodule update

clear || cls

# Locations
ENV_FOLDER="backend"
ALERTMANAGER_FOLDER="alertmanager"
AUTH0JSON_FOLDER="frontend/labyrinth/src/"
CADDYDIR="caddy"

echo "Setting up .env..."

source install_functions.sh

if [ -f "$ENV_FOLDER/.env" ]; then
echo ".env already exists.  Do you want to skip?  Enter is yes, any other entry else will create a new configuration."
read
if [ -z "$REPLY" ]; then
echo "Skipping Auth0 Configuration"
else
auth_zero
fi
else
auth_zero
fi
clear || cls

# auth_config.json - check if exists
# AUTH0DOMAIN -> "domain"
# What is your Auth0 Audience?  This must match exactly.  E.g. http://labyrinth/labyrinth" # audience - this might be the same

# Get these from the existing file

AUTHAPIURL=$(cat $ENV_FOLDER/.env | grep APIURL | sed 's/.*=//g' | xargs)
AUTH0DOMAIN=$(cat $ENV_FOLDER/.env | grep AUTH0DOMAIN | sed 's/.*=//g' | xargs)

echo "Setting up auth_config.json..."

if [ -f "$AUTH0JSON_FOLDER/auth_config.json" ]; then
echo "auth_config.json exists.  Continuing..."
else
    auth_config
fi

clear || cls

# alertmanager.yml.sample - check if exists

if [ -f $ALERTMANAGER_FOLDER/alertmanager.yml ]; then
echo "Alertmanager configuration already found. Overwrite configuration?  Enter is Keep configuration, any other key will create new configuration"
    read
if [ -z "$REPLY" ]; then
echo "Skipping alertmanager configuration..."
else
alertmanager
fi
else
alertmanager
fi

clear || cls

echo "Domain name of this server?"
read
DOMAINNAME=$REPLY

if [ -f $CADDYDIR/.env ]; then
echo "Caddy environment already exists.  Continuing..."
else
echo "Copying over caddy .env..."
cp $CADDYDIR/.env.sample $CADDYDIR/.env
fi

echo "Cloudflare API token for DNS challenge?"
read
sed -i "s|CLOUDFLAREDNS|$REPLY|" $CADDYDIR/.env
sed -i "s|NEWDOMAIN|$DOMAINNAME|" $CADDYDIR/.env

mkdir -p $CADDYDIR/data $CADDYDIR/config

if [ -f $CADDYDIR/Caddyfile ]; then
echo "Leaving Caddyfile as it already exists..."
else
echo "Copying sample Caddyfile..."
cp $CADDYDIR/Caddyfile.sample $CADDYDIR/Caddyfile
fi

clear || cls

# Create docker network
docker network create labyrinth || true

# Compile frontend
echo "Compiling frontend..."
cd frontend && ./publish.sh
cd ..
# Start up with correct docker files
echo "Starting up docker-compose stack..."
docker-compose -f docker-compose-production.yml up --build -d

echo "Done."
