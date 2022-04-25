auth_zero () {
	echo $ENV_FOLDER
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

}

auth_config () {
    cp $AUTH0JSON_FOLDER/auth_config.json.sample $AUTH0JSON_FOLDER/auth_config.json

	echo "What is your Auth0 Client Id?" #clientId
	read;
	sed -i "s|CLIENTID|\"$REPLY\"|" $AUTH0JSON_FOLDER/auth_config.json
	
	sed -i "s|AUDIENCE|\"$AUTHAPIURL\"|" $AUTH0JSON_FOLDER/auth_config.json
	sed -i "s|DOMAIN|\"$AUTH0DOMAIN\"|" $AUTH0JSON_FOLDER/auth_config.json


}

alertmanager() {
	echo "What is your email server? e.g. localhost:25 (Press Enter to skip)"
	read;
	if [ -z "$REPLY" ]; then
		echo "Skipping alertmanager configuration..."
	else
		cp $ALERTMANAGER_FOLDER/alertmanager.sample.yml $ALERTMANAGER_FOLDER/alertmanager.yml

		sed -i "s|SMARTHOST:25|$REPLY|" $ALERTMANAGER_FOLDER/alertmanager.yml

		echo "Who is your Email from?"
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

}