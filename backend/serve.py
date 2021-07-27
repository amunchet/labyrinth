#!/usr/bin/env python3
"""
Labyrinth Web backend
"""
# Permissions scope names
import functools
import os
import json
import socket

import pymongo
import redis
import toml

import metrics as mc

import shutil
import services as svcs

from common import auth
from common.test import unwrap
from flask import Flask, request
from werkzeug.utils import secure_filename
from flask_cors import CORS

import ansible_helper

from concurrent.futures import ThreadPoolExecutor
# DOCS https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
executor = ThreadPoolExecutor(2)


TELEGRAF_KEY = os.environ.get("TELEGRAF_KEY")


def _requires_header(f, permission):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get("Authorization") != permission:
            print("Invalid header!")
            raise Exception("Invalid Header")
        return f(*args, **kwargs)
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

requires_header = functools.partial(_requires_header, permission=TELEGRAF_KEY)


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

# File uploads


valid_type = ["ssh", "totp", "become", "telegraf", "ansible", "other"]


@app.route("/upload/<type>/<override_token>", methods=["POST"])
@requires_auth_admin
def upload(type, override_token):
    """
    Handles file upload
    """
    if type not in valid_type:
        return "Invalid type", 412

    if 'file' not in request.files:
        return "No file included", 407

    file = request.files['file']
    if file.filename == "":
        return "No file selected", 409

    if not os.path.exists("/src/uploads"):
        os.mkdir("/src/uploads")

    if not os.path.exists("/src/uploads/{}".format(type)):
        os.mkdir("/src/uploads/{}".format(type))

    if file:
        filename = secure_filename(file.filename)
        file.save("/tmp/{}".format(filename))
        if ansible_helper.check_file(filename, type):
            shutil.move("/tmp/{}".format(filename),
                        "/src/uploads/{}/{}".format(type, filename))
        else:
            return "File check failed", 521

    return "Success", 200


@app.route("/uploads/<type>", methods=["GET"])
@requires_auth_admin
def list_uploads(type):
    """
    Lists all entries in an upload folder
    """
    if type in valid_type and os.path.exists("/src/uploads/{}".format(type)):
        return json.dumps(os.listdir("/src/uploads/{}".format(type)), default=str), 200
    return "Not found", 409


# Redis handler
@app.route("/redis/")
@requires_auth_read
def read_redis():
    """Returns the output of the redis run"""
    a = redis.Redis(host=os.environ.get("REDIS_HOST"))
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

    if "subnet" not in subnet or subnet["subnet"] == '':
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
    return json.dumps(mongo_client["labyrinth"]["hosts"].find_one({"mac": host}), default=str), 200


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

    subnet = host["subnet"]
    if subnet == "":
        return "No subnet", 418

    if mongo_client["labyrinth"]["hosts"].find_one({"mac": host["mac"]}):
        mongo_client["labyrinth"]["hosts"].delete_one({"mac": host["mac"]})


    if not mongo_client["labyrinth"]["subnets"].find_one({"subnet": subnet}):
        mongo_client["labyrinth"]["subnets"].insert_one({
            "subnet": subnet,
            "origin": {},
            "links": {}
        })

    mongo_client["labyrinth"]["hosts"].insert_one(host)
    return "Success", 200


@app.route("/hosts/")
@requires_auth_read
def list_hosts():
    """Lists all hosts"""
    return json.dumps([x for x in mongo_client["labyrinth"]["hosts"].find({})], default=str), 200


@app.route("/host/<host>", methods=["DELETE"])
@requires_auth_write
def delete_host(host):
    """Deletes a host"""
    result = mongo_client["labyrinth"]["hosts"].delete_one({"$or" : [{"mac": host}, {"ip" : host}]})
    if not result.deleted_count:
        return "Not found", 407
    return "Success", 200

# Services


@app.route("/services/")
@app.route("/services/<all>")
@requires_auth_read
def list_services(all=""):
    """Lists all services"""
    if all == "":
        return json.dumps([x["name"] for x in mongo_client["labyrinth"]["services"].find({})], default=str), 200
    else:
        return json.dumps([x for x in mongo_client["labyrinth"]["services"].find({})], default=str), 200


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
        data = json.loads(request.form.get("data"))
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

# TOML manipulation utilities


@app.route("/redis/put_structure/")
@requires_auth_write
def put_structure():
    """
    Run services generate and store in Redis
    """
    lines = svcs.prepare()
    decoder = toml.TomlPreserveCommentDecoder(beforeComments=True)
    parsed = toml.loads("\n".join(lines), decoder=decoder)
    output = json.dumps(svcs.parse(parsed), default=str)
    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    rc.set("master.data", output)

    # Add in the comments
    full_structure = svcs.find_comments(lines)
    for item in full_structure:
        rc.set(item["name"].replace("]", "").replace("[",
               "").strip(), json.dumps(item, default=str))

    return "Success", 200


@app.route("/redis/get_structure")
@requires_auth_read
def get_structure():
    """
    Retrieves structure from Redis
    """
    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    a = rc.get("master.data")
    if a:
        return a.decode("utf-8"), 200

    # If no structure is loaded, load a structure
    unwrap(put_structure)()
    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    a = rc.get("master.data")
    if a:
        return a.decode("utf-8"), 200

    return "Not found", 424


@app.route("/redis/get_comments/<comment>")
@requires_auth_read
def get_comment(comment):
    """
    Gets a comment
    """
    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    a = rc.get(comment)
    if a:
        return a.decode("utf-8"), 200
    return "Not found", 425

@app.route("/redis/autosave", methods=["GET"])
@requires_auth_admin
def get_autosave(auth_client_id):
    """
    Gets the autosaved content from redis
    """
    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    a = rc.get(auth_client_id)
    if a:
        return a.decode("utf-8"), 200
    return "Not found", 426

@app.route("/redis/autosave", methods=["POST"])
@requires_auth_admin
def autosave(auth_client_id, data=""):
    """
    Autosaves current content
    """
    if data != "":
        parsed_data = data
    elif request.method == "POST": # pragma: no cover
        parsed_data = request.form.get("data")
    else: # pragma: no cover
        return "Invalid", 496
    
    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    a = rc.set(auth_client_id, parsed_data)
    return "Success", 200


# Write host telegraf config file
@app.route("/save_conf/<host>", methods=["POST"])
@requires_auth_admin
def save_conf(host, data=""):
    """
    Saves the Telegraf config file to the given host location
    """
    if data != "":
        parsed_data = data
    elif request.method == "POST": # pragma: no cover
        parsed_data = json.loads(request.form.get("data"))
    else: # pragma: no cover
        return "Invalid", 498

    svcs.output(host, parsed_data)
    return "Success", 200    

# Utilities


@app.route("/find_ip/")
@requires_auth_admin
def find_ip():
    """
    Returns the IP for the docker container
    """
    return socket.gethostbyname(socket.gethostname()), 200


@app.route("/list_directory/<type>")
@requires_auth_admin
def list_directory(type):
    """
    Lists directory
    """

    valid_type = ["ssh", "totp", "become", "telegraf", "ansible", "other"]
    if type not in valid_type:
        return "Invalid type", 446

    if not os.path.exists("/src/uploads/{}".format(type)):
        return "No folder", 447

    return json.dumps(os.listdir("/src/uploads/{}".format(type))), 200


@app.route("/get_ansible_file/<fname>")
@requires_auth_admin
def get_ansible_file(fname):
    """
    Returns the given ansible file
    """
    parsed = fname.replace(".yml", "")
    with open("/src/uploads/ansible/{}.yml".format(parsed)) as f:
        return f.read(), 200


@app.route("/save_ansible_file/<fname>/", methods=["POST"])
@requires_auth_admin
def save_ansible_file(fname, inp_data=""):
    """
    Save Ansible File
        - Have to check if it's a valid ansible file (from `ansible_helper`)
    """
    if inp_data != "":
        data = inp_data
    elif request.method == "POST":  # pragma: no cover
        data = request.form.get("data")
    else:
        return "Invalid request", 417

    filename = "/src/uploads/ansible/{}.yml".format(fname.replace(".yml", ""))
    if ansible_helper.check_file(filename=fname, raw=data, file_type="ansible"):
        return "Success", 200
    else:
        return "Invalid ansible file", 471


# Ansible runner
@app.route("/ansible_runner/", methods=["POST"])
@requires_auth_admin
def run_ansible(inp_data=""):
    if inp_data != "":
        data = inp_data
    elif request.method == "POST":  # pragma: no cover
        data = request.form.get("data")
    else:  # pragma: no cover
        return "Invalid data", 481

    data = json.loads(data)
    if "hosts" not in data or "playbook" not in data or "vault_password" not in data or "become_file" not in data:
        return "Invalid data", 482

    return ansible_helper.run_ansible(data["hosts"], data["playbook"], data["vault_password"], data["become_file"]), 200


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

            if service.strip() == "open_ports" or service.strip() == "closed_ports":
                latest_metric = mongo_client["labyrinth"]["metrics"].find_one(
                    {"name": "open_ports", "tags.host": host["mac"]},
                    sort=[("timestamp", pymongo.DESCENDING)]
                )
                found_service = service

                result = mc.judge_port(latest_metric, service, host)
            else:
                latest_metric = mongo_client["labyrinth"]["metrics"].find_one(
                    {"name": service, "tags.host": host["mac"]},
                    sort=[("timestamp", pymongo.DESCENDING)]
                )
                found_service = mongo_client["labyrinth"]["services"].find_one({
                                                                               "name": service})

                if latest_metric is None or found_service is None:
                    result = False
                else:
                    result = mc.judge(latest_metric, found_service)

            temp = {
                "name": service,
                "state": result
            }
            service_results[service] = {
                "name": service,
                "state": result
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
        for host in sorted([x for x in subnet["hosts"] if "group" in x], key=lambda x: x["ip"]):
            if host["group"] not in groups:
                groups[host["group"]] = []
            groups[host["group"]].append(host)

        if "groups" not in subnet:
            subnet["groups"] = []

        for group in groups:
            subnet["groups"].append({
                "name": group,
                "hosts": groups[group]
            })
        del subnet["hosts"]

    return json.dumps(subnets, default=str), 200

# Metric


@app.route("/metrics/<int:count>", methods=["GET"])
@requires_auth_read
def last_metrics(count):
    """
    Lists the last <count> of metrics
    """
    return json.dumps(
        [x 
        for x in 
            mongo_client["labyrinth"]["metrics"].find({}).sort(
                [("metrics.timestamp", pymongo.ASCENDING)]
            )
        ], default=str), 200


@app.route("/metrics/<host>")
@requires_auth_read
def read_metrics(host):
    """
    Returns the latest metrics for a given host
    """
    return json.dumps([x for x in mongo_client["labyrinth"]["metrics"].find({"tags.host": host})], default=str), 200


@app.route("/metrics/", methods=["POST"])
@requires_header
def insert_metric(inp=""):
    """
    Inserts metric
    """
    if inp != "":
        data = inp
    elif request.method == "POST":  # pragma: no cover
        data = json.loads(request.data.decode("utf-8"))
    else:  # pragma: no cover
        return "Invalid data", 419

    mongo_client["labyrinth"]["metrics"].create_index(
        [("metrics.timestamp", -1)])

    if "metrics" not in data:
        return "Invalid data", 421

    for item in data["metrics"]:
        mongo_client["labyrinth"]["metrics"].insert_one(item)

    return "Success", 200


if __name__ == "__main__":  # Run the Flask server in development mode
    app.debug = True
    app.config["ENV"] = "development"
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7000)))
