#!/bin/bash
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

	echo "What is your Auth0 API Url Identifier? (e.g. http://labyrinth/laybrinth)" # APIURL
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
# What is your Auth0 Audience?  This must match exactly.  E.g. http://labyrinth/laybrinth" # audience - this might be the same

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
	echo "What is your email server (Press Enter to skip)"
	read;
	if [ -z "$REPLY" ]; then
		echo "Skipping alertmanager configuration..."
	else

		cp $ALERTMANAGER_FOLDER/alertmanager.yml.sample $ALERTMANAGER_FOLDER/alertmanager.yml

		sed -i "s|EMAILSERVER|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml
		echo "What is your Email from?"
		echo "What is your email username?"
		echo "What is your email password?"
	fi

fi
exit 1
clear || cls

# Lego - setup defaults to cloudflare
echo "Set up Lego Cloudflare integration? (Press Enter to generate self signed)"

echo "Cloudflare Email?"
echo "Cloudflare API Key?"
echo "Domain?"

clear || cls

# Compile frontend
echo "Compiling frontend..."

# Start up with correct docker files
echo "Starting up docker-compose stack..."

echo "Done."
