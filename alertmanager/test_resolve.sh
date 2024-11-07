#!/bin/sh
url='http://localhost:9093/api/v2/alerts'
name="TEST ALERT"
echo "resolving alert $name" 

PASS=`cat /src/pass`
curl --user admin:$PASS -XPOST $url -d "[{ 
	\"status\": \"resolved\",
	\"labels\": {
		\"alertname\": \"$name\",
		\"service\": \"your-service\",
		\"severity\":\"error\",
		\"instance\": \"$name.example.net\"
	},
    \"endsAt\" : \"`date --iso-8601=seconds`\"
}]"