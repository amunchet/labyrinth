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
    read;
	if [ -z "$REPLY" ]; then
		echo "Skipping alertmanager configuration..."
	else
		alertmanager
	fi	
else
	alertmanager
fi

clear || cls
# Lego - setup defaults to cloudflare
LEGODIR="nginx/.lego"
NGINXDIR="nginx"

echo "Domain name of this server?"
read;
DOMAINNAME=$REPLY


if [ -f $NGINXDIR/.env ]; then
	echo ""
else
	echo "Copying over nginx .env..."
	cp $NGINXDIR/.env.sample $NGINXDIR/.env
fi

if [ -d $LEGODIR ]; then
	echo "Certificates already setup.  Continuing..."
else
	mkdir $LEGODIR || true
	mkdir $LEGODIR/certificates || true


	echo "Set up LetsEncrypt/Cloudflare integration? (Y to continue, press Enter to generate self signed)"
	read;

	if [ -z "$REPLY" ]; then
		echo "Setting up self signed certificate..."

		# Create certificates
		openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 -keyout $LEGODIR/certificates/$DOMAINNAME.key -out $LEGODIR/certificates/$DOMAINNAME.crt

	else
		echo "Setting up LetsEncrypt/Cloudflare integration..."

		echo "Cloudflare Email?"
		read;
		sed -i "s|CLOUDFLAREEMAIL|$REPLY|" $NGINXDIR/.env

		echo "Cloudflare API Key?"
		read;
		sed -i "s|CLOUDFLAREDNS|$REPLY|" $NGINXDIR/.env

		sed -i "s|NEWDOMAIN|$DOMAINNAME|" $NGINXDIR/.env

	fi
fi
if [ -f $NGINXDIR/nginx.conf ]; then
	echo "Leaving nginx.conf as it already exists..."
else
	echo "Adjusting nginx.conf..."
	cp $NGINXDIR/nginx.conf.sample $NGINXDIR/nginx.conf
	sed -i "s|DOMAIN|$DOMAINNAME|g" $NGINXDIR/nginx.conf
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
