#!/bin/sh

# TODO: Need to start the CVE docker stack as well

# Need to create the SSL certs if they don't exist...

echo "Touching nginx/.env..."
touch nginx/.env || true

echo "Creating Development SSL..."
LEGODIR="nginx/.lego"
mkdir $LEGODIR || true

ENV_FOLDER="backend"
ALERTMANAGER_FOLDER="alertmanager"
AUTH0JSON_FOLDER="frontend/labyrinth/src/"

echo "Setting up .env..."

source install_functions.sh

if [ -f "$ENV_FOLDER/.env" ]; then
	echo ".env already exists.  Do you want to skip?  Enter is yes, any other entry else will create a new configuration."
	read;
	if [ -z "$REPLY" ]; then
		echo "Skipping Auth0 Configuration"
	else
		auth_zero
	fi
else
	auth_zero
fi
clear || cls

# Start up alertmanager and
if [ -f "$ALERTMANAGER_FOLDER/alertmanager.yml" ]; then

echo "alertmanager.yml already exists.  Do you want to skip?  Enter is yes, any other entry else will create a new configuration."
	read;
	if [ -z "$REPLY" ]; then
		echo "Skipping Alertmanager Configuration"
	else
		auth_zero
        cp $ALERTMANAGER_FOLDER/alertmanager.sample.yml $ALERTMANAGER_FOLDER/alertmanager.yml
	fi
else
	cp $ALERTMANAGER_FOLDER/alertmanager.sample.yml $ALERTMANAGER_FOLDER/alertmanager.yml
fi

# Auth config JSON file

if [ -f "$AUTH0JSON_FOLDER/auth_config.json" ]; then
	echo "auth_config.json exists.  Continuing..."
else
    auth_config
fi



mkdir $LEGODIR/certificates || true

DOMAINNAME="development"
openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -subj "/C=US/ST=IL/L=Chicago/O=Development/CN=Common" -keyout $LEGODIR/certificates/$DOMAINNAME.key -out $LEGODIR/certificates/$DOMAINNAME.crt

if [ -z "${GITHUB}" ]; then
    echo "Starting development docker..."
    docker-compose -f docker-compose-development.yml up --build -d
else
    echo "[CI] Starting only CI dockers..."

    # .env file - check if exists
    ENV_FOLDER="backend"

    echo "Setting up .env..."

    if [ -f "$ENV_FOLDER/.env" ]; then
        echo ".env already exists.  Continuing."
    else
        cp $ENV_FOLDER/.env.sample $ENV_FOLDER/.env
    fi

    echo "Copying over alertmanager.yml..."
    if [ -f "alertmanager/alertmanager.yml" ]; then
        echo "alertmanager.yml already exists.  Continuing..."
    else
        cp alertmanager/alertmanager.yml.development alertmanager/alertmanager.yml
    fi

    docker-compose -f docker-compose-development.yml up --build -d mongo redis backend alertmanager
fi
