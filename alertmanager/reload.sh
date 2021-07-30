#!/bin/sh
PASS=`cat /src/pass`
curl -X POST --user admin:$PASS http://localhost:9093/-/reload