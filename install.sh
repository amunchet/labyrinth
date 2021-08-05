#!/bin/bash

if [[ $EUID -ne 0 ]]; then
	echo "This script must be run as root" 
	exit 1
fi

echo "Starting production installation."

echo "Initializing submodules..."
git submodule init
git submodule update

clear || cls

# .env file - check if exists
ENV_FOLDER="backend"

echo "Setting up .env..."

if [ -f "$ENV_FOLDER/.env" ]; then
	echo ".env already exists.  Continuing."
else
	cp $ENV_FOLDER/.env.sample $ENV_FOLDER/.env

	echo "What is your Auth0 API Url Identifier? (e.g. http://labyrinth/labyrinth)" # APIURL
	read;
	sed -i "s|=API_URL|=$REPLY|" $ENV_FOLDER/.env

	echo "What is your Auth0 Domain? e.g. dev-xxxxx.auth0.com " # AUTH0DOMAIN
	read;
	sed -i "s|=AUTH0_DOMAIN|=$REPLY|" $ENV_FOLDER/.env

	echo "Enter the key to receive telegraf metrics? E.g. 1234" # TELEGRAF_KEY
	read;
	sed -i "s|=TELEGRAF_KEY|=$REPLY|" $ENV_FOLDER/.env
fi
clear || cls


# auth_config.json - check if exists
# AUTH0DOMAIN -> "domain"
# What is your Auth0 Audience?  This must match exactly.  E.g. http://labyrinth/labyrinth" # audience - this might be the same

# Get these from the existing file
AUTH0JSON_FOLDER="frontend/labyrinth/src/"

AUTHAPIURL=$(cat $ENV_FOLDER/.env | grep APIURL | sed 's/.*=//g' | xargs)
AUTH0DOMAIN=$(cat $ENV_FOLDER/.env | grep AUTH0DOMAIN | sed 's/.*=//g' | xargs) 

echo "Setting up auth_config.json..."

if [ -f "$AUTH0JSON_FOLDER/auth_config.json" ]; then
	echo "auth_config.json exists.  Continuing..."
else
	cp $AUTH0JSON_FOLDER/auth_config.json.sample $AUTH0JSON_FOLDER/auth_config.json

	echo "What is your Auth0 Client Id?" #clientId
	read;
	sed -i "s|CLIENTID|\"$REPLY\"|" $AUTH0JSON_FOLDER/auth_config.json
	
	sed -i "s|AUDIENCE|\"$AUTHAPIURL\"|" $AUTH0JSON_FOLDER/auth_config.json
	sed -i "s|DOMAIN|\"$AUTH0DOMAIN\"|" $AUTH0JSON_FOLDER/auth_config.json

fi
clear || cls

# alertmanager.yml.sample - check if exists
ALERTMANAGER_FOLDER="alertmanager"


if [ -f $ALERTMANAGER_FOLDER/alertmanager.yml ]; then
	echo "Alertmanager configuration already found.  Continuing..."
else
	echo "What is your email server? e.g. localhost:25 (Press Enter to skip)"
	read;
	if [ -z "$REPLY" ]; then
		echo "Skipping alertmanager configuration..."
	else

		cp $ALERTMANAGER_FOLDER/alertmanager.yml.sample $ALERTMANAGER_FOLDER/alertmanager.yml

		sed -i "s|SMARTHOST|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml

		echo "What is your Email from?"
		read;
		sed -i "s|MAILFROM|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml

		echo "What is your email username?"
		read;
		sed -i "s|SMTPUSER|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml

		echo "What is your email password?"
		read;
		sed -i "s|SMTPPASSWORD|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml

		echo "What email should alerts go to by default?"
		read;
		sed -i "s|MAILTO|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml
	fi

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
