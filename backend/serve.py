#!/usr/bin/env python3
"""
Sample Flask app
"""
# Permissions scope names
import functools
import os
import json

import pymongo

from common import auth
from flask import Flask, request
from flask_cors import CORS


PERM_READ = "read"
PERM_WRITE = "write"
PERM_ADMIN = "reports"


requires_auth_read = functools.partial(
    auth._requires_auth, permission=PERM_READ)
requires_auth_write = functools.partial(
    auth._requires_auth, permission=PERM_WRITE)
requires_auth_admin = functools.partial(
    auth._requires_auth, permission=PERM_ADMIN)

app = Flask(__name__)
CORS(app)

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
def insecure():
    return "Insecure route.", 200


@app.route("/secure")
@requires_auth_read
def secure():
    return "Secure route.", 200

# CRUD for network structure


@app.route("/subnets")
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


@app.route("/subnet/<subnet>", methods=["POST"])
@requires_auth_write
def create_edit_subnet(inp=""):
    """Creates/Edits a Subnet"""
    if inp != "":
        subnet = inp
    elif request.method == "POST":  # pragma: no cover
        subnet = request.form.get("data")
    else:
        return "Invalid request", 443

    if "subnet" not in subnet:
        return "Invalid data", 407

    if [x for x in mongo_client["labyrinth"]["subnets"].find({"subnet": subnet["subnet"]})]:
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


@app.route("/host")
@requires_auth_read
def create_edit_host(inp="", methods=["POST"]):
    """Creates/Edits a host"""
    if inp != "":
        host = inp
    elif request.method == "POST":  # pragma: no cover
        host = request.form.get("data")
    else:
        return "Invalid data", 443

    if "mac" not in host:
        return "Invalid data", 407

    if [x for x in mongo_client["labyrinth"]["hosts"].find({"mac": host["mac"]})]:
        mongo_client["labyrinth"]["hosts"].delete_one({"mac": host["mac"]})

    subnet = host["subnet"]

    if not [x for x in mongo_client["labyrinth"]["subnets"].find({"subnet": subnet})]:
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


@app.route("/services")
@requires_auth_read
def list_services():
    """Lists all services"""
    return json.dumps([x["name"] for x in mongo_client["labyrinth"]["services"].find({})], default=str), 200


@app.route("/service/<name>")
@requires_auth_read
def read_service(name):
    """Reads a given service"""
    return json.dumps([x for x in mongo_client["labyrinth"]["services"].find({"name": name})], default=str), 200


@app.route("/service", methods=["POST"])
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
@app.route("/mac/<old_mac>/<new_mac>")
@requires_auth_write
def update_mac(old_mac, new_mac):
    """Updates the old mac to the new mac"""
    mongo_client["labyrinth"]["hosts"].update_one({"mac" : old_mac}, {"$set" : {"mac" : new_mac}})
    return "Success", 200

@app.route("/ip/<mac>/<new_ip>")
@requires_auth_write
def update_ip(mac, new_ip):
    """Updates an IP for a given MAC address"""
    mongo_client["labyrinth"]["hosts"].update_one({"mac" : mac}, {"$set" : {"ip" : new_ip}})
    return "Success", 200


# Dashboard


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
