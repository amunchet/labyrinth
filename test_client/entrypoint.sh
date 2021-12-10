#!/bin/sh

echo "Copying over sample SSH key to authorized..."
mkdir /root/.ssh || true
cat /src/sample_key.pub > /root/.ssh/authorized_keys

echo "Starting SSH server..."
service ssh start

echo "Starting test_client..."
sleep inf