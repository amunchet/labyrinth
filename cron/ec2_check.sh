#!/bin/sh
# EC2 unmatched instance check and alert

cd /src
if [ -f .env ]; then
	set -a;
	source .env;
	set +a;
fi

PYTHONPATH=. python3 ec2_unmatched_check.py 2>&1
