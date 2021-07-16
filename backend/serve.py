#!/usr/bin/env python3
"""
Sample Flask app
"""
# Permissions scope names
import functools
import os
import json

import pymongo
import redis

import metrics as mc

from common import auth
from common.test import unwrap
from flask import Flask, request
from flask_cors import CORS

from concurrent.futures import ThreadPoolExecutor
# DOCS https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
executor = ThreadPoolExecutor(2)


TELEGRAF_KEY=os.environ.get("TELEGRAF_KEY")

def _requires_header(f, permission):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get("Authorization") != permission:
            raise Exception("Invalid Header")
    
    return decorated


app = Flask(__name__)
CORS(app)

PERM_READ = "read"
PERM_WRITE = "write"
PERM_ADMIN = "admin"

@app.route("/error/<int:code>")
def error_func(code=401, msg="", command=""):  # pragma: no cover
    if isinstance(code, int):
        return "Auth Error {} - {}".format(code, msg), code
    return "Auth Error", 500


requires_auth_read = functools.partial(
    auth._requires_auth, permission=PERM_READ, error_func=error_func
)
requires_auth_write = functools.partial(
    auth._requires_auth, permission=PERM_WRITE, error_func=error_func
)
requires_auth_admin = functools.partial(
    auth._requires_auth, permission=PERM_ADMIN, error_func=error_func
)

requires_header = functools.partial(_requires_header, permission = TELEGRAF_KEY)


# Mongo Access
mongo_client = pymongo.MongoClient(
    "mongodb://{}:{}@{}:27017".format(
        os.environ.get("MONGO_USERNAME"),
        os.environ.get("MONGO_PASSWORD"),
        os.environ.get("MONGO_HOST"),
    )
)

# Route definitions


@app.route("/insecure")
@app.route("/insecure/")
def insecure():

    return "Insecure route.", 200

@app.route("/secure/")
@app.route("/secure")
@requires_auth_read
def secure():
    return "Secure route.", 200

# Redis handler
@app.route("/redis/")
@requires_auth_read
def read_redis():
    """Returns the output of the redis run"""
    a = redis.Redis(host="redis")
    b = a.get("output")
    if b:
        return b
    return "[No output found]", 200

# Scan handler
@app.route("/scan/")
@requires_auth_write
def scan():
    """Runs NMAP Scan"""

    from finder import main
    executor.submit(main)
    return "Scan Started.", 200

# CRUD for network structure


@app.route("/subnets/")
@requires_auth_read
def list_subnets():
    """
    Lists all the subnets
    """
    return json.dumps(
        [
            x["subnet"]
            for x in mongo_client["labyrinth"]["subnets"].find({})
        ], default=str), 200


@app.route("/subnet/<subnet>")
@requires_auth_read
def list_subnet(subnet=""):
    """List contents of a given subnet"""
    x = [x for x in mongo_client["labyrinth"]
         ["subnets"].find({"subnet": subnet})]
    if not x:
        return "No subnet found", 404
    if len(x) > 1:  # pragma: no cover
        return "Too many subnets found", 405

    return json.dumps(x[0], default=str), 200


@app.route("/subnet/", methods=["POST"])
@requires_auth_write
def create_edit_subnet(inp=""):
    """Creates/Edits a Subnet"""
    if inp != "":
        subnet = inp
    elif request.method == "POST":  # pragma: no cover
        subnet = json.loads(request.form.get("data"))
    else:
        return "Invalid request", 443

    if "subnet" not in subnet:
        return "Invalid data", 407

    if mongo_client["labyrinth"]["subnets"].find_one({"subnet": subnet["subnet"]}):
        mongo_client["labyrinth"]["subnets"].delete_one(
            {"subnet": subnet["subnet"]})

    mongo_client["labyrinth"]["subnets"].insert_one(subnet)
    return "Success", 200


@app.route("/subnet/<subnet>", methods=["DELETE"])
@requires_auth_write
def delete_subnet(subnet):
    """Deletes a subnet"""
    result = mongo_client["labyrinth"]["subnets"].delete_one(
        {"subnet": subnet})
    if not result.deleted_count:
        return "Not found", 407
    return "Success", 200

# Links


@app.route("/link/<subnet>", methods=["POST"])
@requires_auth_write
def create_edit_link(subnet="", link=""):
    data = {}
    if subnet != "" and link != "":
        data["subnet"] = subnet
        data["link"] = link
    elif request.method == "POST":  # pragma: no cover
        data["subnet"] = subnet
        data["link"] = request.form.get("link")
    else:
        return "Invalid", 417

    mongo_client["labyrinth"]["subnets"].update_one(
        {"subnet": data["subnet"]},
        {"$set": {"links": data["link"]}}
    )
    return "Success", 200

# Hosts

@app.route("/host/<host>", methods=["GET"])
@requires_auth_read
def list_host(host=""):
    return json.dumps(mongo_client["labyrinth"]["hosts"].find_one({"mac" : host}), default=str), 200


@app.route("/host/", methods=["POST"])
@requires_auth_read
def create_edit_host(inp=""):
    """Creates/Edits a host"""
    if inp != "":
        host = inp
    elif request.method == "POST":  # pragma: no cover
        host = json.loads(request.form.get("data"))
    else:
        return "Invalid data", 443

    if "mac" not in host:
        return "Invalid data", 407

    if mongo_client["labyrinth"]["hosts"].find_one({"mac": host["mac"]}):
        mongo_client["labyrinth"]["hosts"].delete_one({"mac": host["mac"]})

    subnet = host["subnet"]

    if not mongo_client["labyrinth"]["subnets"].find_one({"subnet": subnet}):
        mongo_client["labyrinth"]["subnets"].insert_one({
            "subnet": subnet,
            "origin": {},
            "links": {}
        })

    mongo_client["labyrinth"]["hosts"].insert_one(host)
    return "Success", 200


@app.route("/host/<host>", methods=["DELETE"])
@requires_auth_write
def delete_host(host):
    """Deletes a host"""
    result = mongo_client["labyrinth"]["hosts"].delete_one({"mac": host})
    if not result.deleted_count:
        return "Not found", 407
    return "Success", 200

# Services


@app.route("/services/")
@requires_auth_read
def list_services():
    """Lists all services"""
    return json.dumps([x["name"] for x in mongo_client["labyrinth"]["services"].find({})], default=str), 200


@app.route("/service/<name>")
@requires_auth_read
def read_service(name):
    """Reads a given service"""
    return json.dumps([x for x in mongo_client["labyrinth"]["services"].find({"name": name})], default=str), 200


@app.route("/service/", methods=["POST"])
@requires_auth_write
def create_edit_service(service=""):
    """Creates/Edits a Service"""
    if service != "":
        data = service
    elif request.method == "POST":  # pragma: no cover
        data = request.form.get("data")
    else:
        return "Invalid", 427

    if "name" not in data:
        return "Invalid data", 439

    if [x for x in mongo_client["labyrinth"]["services"].find({"name": data["name"]})]:
        mongo_client["labyrinth"]["services"].delete_one(
            {"name": data["name"]})

    mongo_client["labyrinth"]["services"].insert_one(data)

    return "Success", 200


@app.route("/service/<name>", methods=["DELETE"])
@requires_auth_write
def delete_service(name):
    """
    Deletes a service
        - Also deletes a snippet if it exists
        - Removes service from all hosts if they have it
    """
    # Delete Service
    mongo_client["labyrinth"]["services"].delete_one({"name": name})

    # Check for hosts that had the service
    mongo_client["labyrinth"]["hosts"].update_many(
        {"services": {
            "$in": [name]
        }},
        {
            "$pull": {
                "services": name
            }
        }
    )
    # Check if snippet exists
    if os.path.exists("/src/snippets/{}".format(name)):
        os.remove("/src/snippets/{}".format(name))

    return "Success", 200

# Utilities


@app.route("/mac/<old_mac>/<new_mac>/")
@requires_auth_write
def update_mac(old_mac, new_mac):
    """Updates the old mac to the new mac"""
    mongo_client["labyrinth"]["hosts"].update_one(
        {"mac": old_mac}, {"$set": {"mac": new_mac}})
    return "Success", 200


@app.route("/ip/<mac>/<new_ip>/")
@requires_auth_write
def update_ip(mac, new_ip):
    """Updates an IP for a given MAC address"""
    mongo_client["labyrinth"]["hosts"].update_one(
        {"mac": mac}, {"$set": {"ip": new_ip}})
    return "Success", 200

# Dashboard


@app.route("/dashboard/")
@requires_auth_read
def dashboard():
    """Dashboard"""
    # Get all the subnets
    subnets = {}
    for item in json.loads(unwrap(list_subnets)()[0]):
        subnets[item] = {}

    for item in subnets.keys():
        subnets[item] = json.loads(unwrap(list_subnet)(item)[0])

    # Get all the hosts
    hosts = [x for x in mongo_client["labyrinth"]["hosts"].find({})]


    # Get the hosts latest metrics for states
    for host in [x for x in hosts if "services" in x]:
        service_results = {}
        for service in host["services"]:
            latest_metric = mongo_client["labyrinth"]["metrics"].find_one(
                {"name": service, "tags.host": host["mac"]},
                sort=[("timestamp", pymongo.DESCENDING)]
            )

            found_service = mongo_client["labyrinth"]["services"].find_one({"name" : service})
            
            if latest_metric is None or found_service is None:
                result = False
            else:
                result = mc.judge(latest_metric, found_service)
            
            temp = {
                "name" : service,
                "state" : result
            }
            service_results[service] = {
                "name": service,
                "state" : result
            }
        for item in service_results:
            host["services"] = [service_results[x] for x in service_results]
        

    # Sort hosts into subnets
    for item in hosts:
        if "subnet" in item and item["subnet"] in subnets:
            if "hosts" not in subnets[item["subnet"]]:
                subnets[item["subnet"]]["hosts"] = []
            subnets[item["subnet"]]["hosts"].append(item)

    # Within each subnet, sort into groups
    subnets = [subnets[x] for x in subnets]
    for subnet in [x for x in subnets if "hosts" in x]:
        groups = {}
        for host in [x for x in subnet["hosts"] if "group" in x]:
            if host["group"] not in groups:
                groups[host["group"]] = []
            groups[host["group"]].append(host)

        if "groups" not in subnet:
            subnet["groups"] = []

        for group in groups:
            subnet["groups"].append({
                "name" : group,
                "hosts" : groups[group]
            })
        del subnet["hosts"]

    return json.dumps(subnets, default=str), 200

# Metrics

@app.route("/metrics/<host>")
@requires_auth_read
def read_metrics(host):
    """
    Returns the latest metrics for a given host
    """
    return json.dumps([x for x in mongo_client["labyrinth"]["metrics"].find({"tags.host" : host})], default=str), 200

@app.route("/metrics/", methods=["POST"])
@requires_header
def insert_metric(inp=""):
    """
    Inserts metric
    """
    if inp != "":
        data = inp
    elif request.method == "POST": # pragma: no cover
        data = request.form.get("data")
    else: # pragma: no cover
        return "Invalid data", 419
    
    mongo_client["labyrinth"]["metrics"].create_index([ ("metrics.timestamp", -1) ])
    
    if "metrics" not in data:
        return "Invalid data", 421
    
    for item in data["metrics"]:
        mongo_client["labyrinth"]["metrics"].insert_one(item)
    
    return "Success", 200



# Ansible
"""
>>> a = ansible_runner.run(private_data_dir="/src/test/ansible", playbook="install.yml", cmdline="--vault-password-file ../vault.pass")
>>> b = "\n".join([x for x in a.stdout])
>>> c = aconv().convert(b).replace("\x1b[", "")
>>> with open('test.html', 'w') as f:
...     f.write(c)
...
3398
>>> aconv
<class 'ansi2html.converter.Ansi2HTMLConverter'>
"""

if __name__ == "__main__":  # Run the Flask server in development mode
    app.debug = True
    app.config["ENV"] = "development"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7000)))
