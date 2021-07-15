#!/bin/sh
# echo "Generating SSL Certificate..."
# openssl req -subj '/O=My Company Name LTD./C=US/CN=domain.com' -new -newkey rsa:2048 -sha256 -days 365 -nodes -x509 -keyout /etc/nginx/sol.key -out /etc/nginx/sol.crt

echo "Installing CURL..."
apt-get update && apt-get -y install curl 
echo "Starting Nginx..."
service nginx stop && nginx -g 'daemon off;'