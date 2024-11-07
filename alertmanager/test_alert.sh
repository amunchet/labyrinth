#!/bin/sh
url='http://localhost:9093/api/v2/alerts'
name="TEST ALERT"
echo "firing up alert $name" 

PASS=`cat /src/pass`

# change url o
curl --user admin:$PASS -XPOST $url -d "[{ 
	\"status\": \"firing\",
	\"labels\": {
		\"alertname\": \"$name\",
		\"service\": \"your-service\",
		\"severity\":\"error\",
		\"instance\": \"$name.example.net\"
	},
	\"annotations\": {
		\"summary\": \"High latency is low!\"
	},
	\"generatorURL\": \"http://prometheus.int.example.net/<generating_expression>\"
}]"
echo ""