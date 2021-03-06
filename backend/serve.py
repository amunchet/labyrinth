#!/usr/bin/env python3
"""
Labyrinth Web backend
"""
# Permissions scope names
import functools
import os
import sys
import json
import socket
import datetime
import time

import pymongo
import redis
import toml
import requests
import yaml

import metrics as mc
import watcher

import shutil
import services as svcs

from common import auth
from common.test import unwrap
from flask import Flask, request, Response
from werkzeug.utils import secure_filename
from flask_cors import CORS

import ansible_helper

from concurrent.futures import ThreadPoolExecutor

# DOCS https://docs.python.org/3/library/concurrent.futures.html#concurrent.futures.ThreadPoolExecutor
executor = ThreadPoolExecutor(2)


TELEGRAF_KEY = os.environ.get("TELEGRAF_KEY") or "TEST"


def _requires_header(f, permission):  # pragma: no cover
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
def upload(type, override_token):  # pragma: no cover
    """
    Handles file upload
        - Two types: straight upload and form data upload
        - Form data upload comes from manual additions of vault files
    """
    if type not in valid_type:
        return "Invalid type", 412

    if "file" not in request.files and "file" not in request.form:
        return "No file included", 407

    file = ""
    data = ""
    filename = ""

    if "file" in request.files:
        file = request.files["file"]
    else:
        data = request.form["file"]
        filename = request.form["filename"]

    if file != "" and file.filename == "":
        return "No file selected", 409

    if not os.path.exists("/src/uploads"):
        os.mkdir("/src/uploads")

    if not os.path.exists("/src/uploads/{}".format(type)):
        os.mkdir("/src/uploads/{}".format(type))

    if data:
        with open("/tmp/{}".format(filename), "w") as f:
            f.write(data)

        if os.path.exists(
            "/src/uploads/become/{}.yml".format(filename.replace(".yml", ""))
        ):
            os.remove("/src/uploads/become/{}.yml".format(filename.replace(".yml", "")))

        if ansible_helper.check_file(filename, type):
            shutil.move(
                "/tmp/{}".format(filename),
                "/src/uploads/become/{}.yml".format(filename.replace(".yml", "")),
            )
            return filename, 200
        os.remove("/tmp/{}".format(filename))
        return "File check failed", 522

    elif file:
        filename = secure_filename(file.filename)
        file.save("/tmp/{}".format(filename))
        if ansible_helper.check_file(filename, type):
            shutil.move(
                "/tmp/{}".format(filename), "/src/uploads/{}/{}".format(type, filename)
            )
        else:
            return "File check failed", 521

    # Chmod
    chmod_filename = "/src/uploads/{}/{}".format(type, filename)
    os.chmod(chmod_filename, 0o600)
    return file.filename, 200


@app.route("/uploads/<type>", methods=["GET"])
@requires_auth_admin
def list_uploads(type):
    """
    Lists all entries in an upload folder
    """
    if type in valid_type:
        if not os.path.exists("/src/uploads/{}".format(type)):
            os.mkdir("/src/uploads/{}".format(type))
        return json.dumps(os.listdir("/src/uploads/{}".format(type)), default=str), 200
    return "Not found", 409


# Scan handler


@app.route("/scan/")
@requires_auth_write
def scan():  # pragma: no cover
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
    return (
        json.dumps(
            [x["subnet"] for x in mongo_client["labyrinth"]["subnets"].find({})],
            default=str,
        ),
        200,
    )


@app.route("/subnet/<subnet>")
@requires_auth_read
def list_subnet(subnet=""):
    """List contents of a given subnet"""
    x = [x for x in mongo_client["labyrinth"]["subnets"].find({"subnet": subnet})]
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
    else:  # pragma: no cover
        return "Invalid request", 443

    if "subnet" not in subnet or subnet["subnet"] == "":  # pragma: no cover
        return "Invalid data", 407

    if mongo_client["labyrinth"]["subnets"].find_one({"subnet": subnet["subnet"]}):
        mongo_client["labyrinth"]["subnets"].delete_one({"subnet": subnet["subnet"]})

    mongo_client["labyrinth"]["subnets"].insert_one(subnet)
    return "Success", 200


@app.route("/subnet/<subnet>", methods=["DELETE"])
@requires_auth_write
def delete_subnet(subnet):
    """Deletes a subnet"""
    result = mongo_client["labyrinth"]["subnets"].delete_one({"subnet": subnet})
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
    else:  # pragma: no cover
        return "Invalid", 417

    mongo_client["labyrinth"]["subnets"].update_one(
        {"subnet": data["subnet"]}, {"$set": {"links": data["link"]}}
    )
    return "Success", 200


# Hosts


@app.route("/host/<host>", methods=["GET"])
@requires_auth_read
def list_host(host=""):
    return (
        json.dumps(
            mongo_client["labyrinth"]["hosts"].find_one({"mac": host}), default=str
        ),
        200,
    )


@app.route("/host/", methods=["POST"])
@requires_auth_read
def create_edit_host(inp=""):
    """Creates/Edits a host"""
    if inp != "":
        host = inp
    elif request.method == "POST":  # pragma: no cover
        host = json.loads(request.form.get("data"))
    else:  # pragma: no cover
        return "Invalid data", 443

    if "mac" not in host:  # pragma: no cover
        return "Invalid data", 407

    subnet = host["subnet"]
    if subnet == "":  # pragma: no cover
        return "No subnet", 418

    if mongo_client["labyrinth"]["hosts"].find_one({"mac": host["mac"]}):
        mongo_client["labyrinth"]["hosts"].delete_one({"mac": host["mac"]})

    if not mongo_client["labyrinth"]["subnets"].find_one({"subnet": subnet}):
        mongo_client["labyrinth"]["subnets"].insert_one(
            {"subnet": subnet, "origin": {}, "links": {}}
        )

    mongo_client["labyrinth"]["hosts"].insert_one(host)
    return "Success", 200


@app.route("/hosts/")
@requires_auth_read
def list_hosts():
    """Lists all hosts"""
    return (
        json.dumps(
            [x for x in mongo_client["labyrinth"]["hosts"].find({})], default=str
        ),
        200,
    )


@app.route("/host/<host>", methods=["DELETE"])
@requires_auth_write
def delete_host(host):
    """Deletes a host"""
    result = mongo_client["labyrinth"]["hosts"].delete_one(
        {"$or": [{"mac": host}, {"ip": host}]}
    )
    if not result.deleted_count:
        return "Not found", 407
    return "Success", 200


@app.route("/host_group_rename/<ip>/<group>/")
@requires_auth_write
def host_group_rename(ip, group):
    """
    Changes the specific host's group name
    """
    found = mongo_client["labyrinth"]["hosts"].find_one({"ip": ip})
    if not found:
        return "Not found", 498
    mongo_client["labyrinth"]["hosts"].update_many(
        {"ip": ip}, {"$set": {"group": group}}
    )
    return "Success", 200


# Group (Mass actions)


@app.route("/group/<subnet>")
@requires_auth_read
def list_subnets_groups(subnet):
    """
    Lists groups present in a subnet
    """
    z = [
        y
        for y in set(
            [
                x["group"]
                for x in mongo_client["labyrinth"]["hosts"].find({"subnet": subnet})
                if "group" in x
            ]
        )
    ]
    return json.dumps(z, default=str), 200


@app.route("/group/<subnet>/<group>")
@requires_auth_read
def list_subnets_group_members(subnet, group):
    """
    Lists group members present in a subnet
    """
    z = [
        y
        for y in set(
            [
                x["ip"]
                for x in mongo_client["labyrinth"]["hosts"].find(
                    {"subnet": subnet, "group": group}
                )
                if "group" in x
            ]
        )
    ]
    return json.dumps(z, default=str), 200


@app.route("/group/monitor/<subnet>/<name>/<status>")
@requires_auth_write
def group_monitor(subnet, name, status):
    """
    Changes the monitoring option for all memebers of the group
    """

    mongo_client["labyrinth"]["hosts"].update_many(
        {"subnet": subnet, "group": name},
        {"$set": {"monitor": str(status).lower() == "true"}},
    )
    return "Updated Monitoring to " + str(str(status).lower() == "true"), 200


@app.route("/group/name/<subnet>/<name>/<new_name>")
@requires_auth_write
def group_rename(subnet, name, new_name):
    """
    Changes name for all members of the group
    """
    mongo_client["labyrinth"]["hosts"].update_many(
        {"subnet": subnet, "group": name}, {"$set": {"group": new_name}}
    )
    return "Success", 200


@app.route("/group/icons/<subnet>/<name>/<new_icon>")
@requires_auth_write
def group_icon(subnet, name, new_icon):
    """
    Change icons
    """

    mongo_client["labyrinth"]["hosts"].update_many(
        {"subnet": subnet, "group": name}, {"$set": {"icon": new_icon}}
    )
    return "Success", 200


@app.route("/group/add_service/<subnet>/<name>/<new_service>")
@requires_auth_write
def group_add_service(subnet, name, new_service):
    """
    Add Service to all members (check if already have it)
    """
    a = mongo_client["labyrinth"]["hosts"].find({"subnet": subnet, "group": name})
    for x in [x for x in a]:
        if new_service not in x["services"]:
            temp = x["services"] + [new_service]
            mongo_client["labyrinth"]["hosts"].update_one(
                {"subnet": subnet, "group": name, "ip": x["ip"]},
                {"$set": {"services": temp}},
            )
    return "Success", 200


@app.route("/group/delete_service/<subnet>/<name>/<new_service>")
@requires_auth_write
def group_delete_service(subnet, name, new_service):
    """
    Deletes Service to all members (check if already have it)
    """
    a = mongo_client["labyrinth"]["hosts"].find({"subnet": subnet, "group": name})
    for x in [x for x in a]:
        if new_service in x["services"]:
            temp = [y for y in x["services"] if y != new_service]
            mongo_client["labyrinth"]["hosts"].update_one(
                {"subnet": subnet, "group": name, "ip": x["ip"]},
                {"$set": {"services": temp}},
            )
    return "Success", 200


# Services


@app.route("/services/")
@app.route("/services/<all>")
@requires_auth_read
def list_services(all=""):
    """Lists all services"""
    if all == "":
        return (
            json.dumps(
                [x["name"] for x in mongo_client["labyrinth"]["services"].find({})],
                default=str,
            ),
            200,
        )
    else:
        return (
            json.dumps(
                [x for x in mongo_client["labyrinth"]["services"].find({})], default=str
            ),
            200,
        )


@app.route("/service/<name>")
@requires_auth_read
def read_service(name):
    """Reads a given service"""
    return (
        json.dumps(
            [x for x in mongo_client["labyrinth"]["services"].find({"name": name})],
            default=str,
        ),
        200,
    )


@app.route("/service/", methods=["POST"])
@requires_auth_write
def create_edit_service(service=""):
    """Creates/Edits a Service"""
    if service != "":
        data = service
    elif request.method == "POST":  # pragma: no cover
        data = json.loads(request.form.get("data"))
    else:  # pragma: no cover
        return "Invalid", 427

    if "name" not in data:  # pragma: no cover
        return "Invalid data", 439

    if [x for x in mongo_client["labyrinth"]["services"].find({"name": data["name"]})]:
        mongo_client["labyrinth"]["services"].delete_one({"name": data["name"]})

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
        {"services": {"$in": [name]}}, {"$pull": {"services": name}}
    )
    # Check if snippet exists
    if os.path.exists("/src/snippets/{}".format(name)):
        os.remove("/src/snippets/{}".format(name))

    return "Success", 200


# Redis
@app.route("/redis/")
@requires_auth_read
def read_redis():
    """Returns the output of the redis run"""
    a = redis.Redis(host=os.environ.get("REDIS_HOST"))
    b = a.get("output")
    if b:
        return b, 200
    return "[No output found]", 200


# Redis - TOML


@app.route("/redis/put_structure")
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
        rc.set(
            item["name"].replace("]", "").replace("[", "").strip(),
            json.dumps(item, default=str),
        )

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

    return "Not found", 424  # pragma: no cover


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
    return "Not found", 425  # pragma: no cover


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
    return "Not found", 426  # pragma: no cover


@app.route("/redis/autosave", methods=["POST"])
@requires_auth_admin
def autosave(auth_client_id, data=""):
    """
    Autosaves current content
    """
    if data != "":
        parsed_data = data
    elif request.method == "POST":  # pragma: no cover
        parsed_data = request.form.get("data")
    else:  # pragma: no cover
        return "Invalid", 496

    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    a = rc.set(auth_client_id, parsed_data)
    return "Success", 200


# Write host telegraf config file
@app.route("/save_conf/<host>", methods=["POST"])
@requires_auth_admin
def save_conf(host, data="", raw=""):
    """
    Saves the Telegraf config file to the given host location
    """
    if data != "" or raw != "":
        parsed_data = data
        parsed_raw = raw
    elif request.method == "POST":  # pragma: no cover
        parsed_data = json.loads(request.form.get("data"))
        parsed_raw = request.form.get("raw")
    else:  # pragma: no cover
        return "Invalid", 498

    svcs.output(host, parsed_data, parsed_raw)
    return "Success", 200


# Run Telegraf configuration test
@app.route("/run_conf/<fname>/<int:testing>")
@requires_auth_admin
def run_telegraf(fname, testing):
    """
    Runs specified telegraf file
    """
    return svcs.run(fname, testing == 1), 200


# Load TOML file
@app.route("/load_service/<name>")
@app.route("/load_service/<name>/<format>")
@requires_auth_admin
def load_service(name, format="json"):
    """
    Loads in a TOML service file
    """
    return svcs.load(name, format), 200


# Alertmanager


@app.route("/alertmanager/pass")
@requires_auth_admin
def alertmanager_pass():
    """Returns contents of the password file"""
    return open("/alertmanager/pass").read(), 200


@app.route("/alertmanager/", methods=["GET"])
@app.route("/alertmanager/<fname>", methods=["GET"])
@requires_auth_admin
def alertmanager_load(fname=""):
    """Return contents of configuration file"""
    url = "/alertmanager/alertmanager.yml"
    if fname != "":
        url = "/alertmanager/{}.yml".format(fname.replace(".yml", ""))
    if not os.path.exists(url):
        return "", 200
    return open(url).read(), 200


@app.route("/alertmanager/", methods=["POST"])
@requires_auth_admin
def alertmanager_save(data=""):
    """Saves alertmanager file"""
    if data != "":
        parsed_data = data
    elif request.method == "POST":  # pragma: no cover
        parsed_data = request.form.get("data")
    else:  # pragma: no cover
        return "Invalid", 483

    with open("/alertmanager/alertmanager.yml", "w") as f:
        f.write(parsed_data)

    return "Success", 200


@app.route("/alertmanager/alerts")
@requires_auth_admin
def list_alerts():
    """
    List all active alerts
    """
    url = "http://alertmanager:9093/api/v2/alerts"
    password = open("/alertmanager/pass").read()

    return json.dumps(requests.get(url, auth=("admin", password)).json()), 200


@app.route("/alertmanager/alert", methods=["POST"])
@requires_auth_admin
def resolve_alert(data=""):
    """
    Resolves a given alert
    """
    if data != "":
        parsed_data = data
    elif request.method == "POST":  # pragma: no cover
        parsed_data = json.loads(request.form.get("data"))
    else:  # pragma: no cover
        return "Invalid data", 419

    url = "http://alertmanager:9093/api/v1/alerts"
    password = open("/alertmanager/pass").read()

    del parsed_data["startsAt"]
    parsed_data["status"] = "resolved"
    parsed_data["endsAt"] = "2021-08-03T14:34:41-05:00"

    retval = requests.post(
        url, data=json.dumps([parsed_data]), auth=("admin", password)
    )

    return retval.text, retval.status_code


@app.route("/alertmanager/restart", methods=["GET"])
@requires_auth_admin
def restart_alertmanager():
    """
    Restarts the alertmanager
    """
    url = "http://alertmanager:9093/-/reload"
    password = open("/alertmanager/pass").read()

    retval = requests.post(url, auth=("admin", password))
    return retval.text, retval.status_code


# Settings
@app.route("/telegraf_key/")
@requires_auth_admin
def telegraf_key():  # pragma: no cover
    """
    Returns Telegraf Key
    """
    return str(TELEGRAF_KEY), 200


@app.route("/settings")
@app.route("/settings/<setting>", methods=["GET"])
@requires_auth_read
def get_setting(setting=""):
    """
    Returns given settings
    """
    if setting == "":
        z = [
            {x["name"]: x["value"]}
            for x in mongo_client["labyrinth"]["settings"].find({})
        ]
        return json.dumps(z, default=str), 200
    else:
        a = mongo_client["labyrinth"]["settings"].find_one({"name": setting})

        if a:
            return a["value"], 200
        return "No results", 481


@app.route("/settings", methods=["POST"])
@app.route("/settings/", methods=["POST"])
@requires_auth_admin
def save_setting(name="", value=""):
    if name != "" and value != "":
        parsed_name, parsed_value = name, value
    elif request.method == "POST":  # pragma: no cover
        parsed_name = request.form.get("name")
        parsed_value = request.form.get("value")
    else:  # pragma: no cover
        return "Invalid", 497

    if mongo_client["labyrinth"]["settings"].find_one({"name": parsed_name}):
        mongo_client["labyrinth"]["settings"].delete_one({"name": parsed_name})

    mongo_client["labyrinth"]["settings"].insert_one(
        {"name": parsed_name, "value": parsed_value}
    )

    return "Success", 200


@app.route("/settings/<setting>", methods=["DELETE"])
@requires_auth_admin
def delete_setting(setting):
    """
    Deletes a setting
    """
    if mongo_client["labyrinth"]["settings"].find_one({"name": setting}):
        mongo_client["labyrinth"]["settings"].delete_one({"name": setting})

    return "Success", 200


# Icons
def check_extension(fname):
    """
    Checks icon extensions
    """
    extensions = [".svg", ".png", ".bmp", ".jpg", ".jpeg"]
    for ext in extensions:
        if ext in fname:
            return True
    return False


@app.route("/icons/")
@requires_auth_admin
def list_icons():
    """Lists Icons"""
    return (
        json.dumps(
            [
                x.replace(".svg", "")
                for x in os.listdir("/public/icons")
                if check_extension(x)
            ],
            default=str,
        ),
        200,
    )


@app.route("/icon/<name>", methods=["DELETE"])
@requires_auth_admin
def delete_icon(name):
    """
    Deletes an icon
    """
    del_files = [
        x
        for x in os.listdir("/public/icons")
        if x.split("/")[-1].split(".")[0] == name and check_extension(x)
    ]
    for fname in del_files:
        os.remove(os.path.join("/public/icons", fname.split("/")[-1]))
    return "Success", 200


@app.route("/icon/<name>", methods=["POST"])
@requires_auth_admin
def create_icon():  # pragma: no cover
    """
    Creates an icon
    """


# Utilities


@app.route("/find_ip/")
@app.route("/find_ip/<name>")
@requires_auth_admin
def find_ip(name=""):
    """
    Returns the IP for the docker container
    """
    if name is None or name == "":
        return socket.gethostbyname(socket.gethostname()), 200
    else:
        return socket.gethostbyname(name), 200


@app.route("/list_directory/<type>")
@requires_auth_admin
def list_directory(type):
    """
    Lists directory
    """

    if type not in valid_type:  # pragma: no cover
        return "Invalid type", 446

    if not os.path.exists("/src/uploads/{}".format(type)):  # pragma: no cover
        return "No folder", 447

    return json.dumps(os.listdir("/src/uploads/{}".format(type))), 200


@app.route("/new_ansible_file/<fname>")
@requires_auth_admin
def new_ansible_file(fname):
    """
    Creates a new ansible file
    """
    filename = "/src/uploads/ansible/{}.yml".format(fname.replace(".yml", ""))
    if os.path.exists(filename):
        return "File already exists", 407
    with open(filename, "w") as f:
        f.write("")
    return filename, 200


@app.route("/get_ansible_file/<fname>")
@requires_auth_admin
def get_ansible_file(fname):
    """
    Returns the given ansible file
    """
    parsed = fname.replace(".yml", "")
    with open("/src/uploads/ansible/{}.yml".format(parsed)) as f:
        return f.read(), 200


@app.route("/save_ansible_file/<fname>/<vars_file>", methods=["POST"])
@requires_auth_admin
def save_ansible_file(fname, inp_data="", vars_file=""):
    """
    Save Ansible File
        - Have to check if it's a valid ansible file (from `ansible_helper`)
        - Handle `vars_files` in hosts
    """
    if inp_data != "":
        data = inp_data
    elif request.method == "POST":  # pragma: no cover
        data = request.form.get("data")
    else:  # pragma: no cover
        return "Invalid request", 417

    filename = "/src/uploads/ansible/{}.yml".format(fname.replace(".yml", ""))

    # Check YAML file
    if vars_file != "":
        try:
            parsed = yaml.safe_load_all(data)
        except yaml.YAMLError as exc:
            return "YAML Read Error: {}".format(exc), 471
        parsed = list(parsed)[0]
        for item in parsed:
            item["vars_files"] = ["/src/uploads/become/{}.yml".format(vars_file)]

        try:
            data = yaml.safe_dump(parsed, sort_keys=False)
        except yaml.YAMLError as exc:
            return "YAML Dump Error: {}".format(exc), 471

    x = ansible_helper.check_file(filename=fname, raw=data, file_type="ansible")
    if type(x) == type([]) and x[0]:
        return "Success", 200
    elif type(x) == type(True) and x:
        return "Success", 200
    else:
        if type(x) == type([]):
            return json.dumps(x, default=str), 471
        else:
            return "Invalid ansible file", 471


# Ansible runner
@app.route("/ansible_runner/", methods=["POST"])
@requires_auth_admin
def run_ansible(inp_data=""):  # pragma: no cover
    if inp_data != "":
        data = inp_data
    elif request.method == "POST":  # pragma: no cover
        data = request.form.get("data")
    else:  # pragma: no cover
        return "Invalid data", 481

    data = json.loads(data)
    if (
        "hosts" not in data
        or "playbook" not in data
        or "vault_password" not in data
        or "become_file" not in data
    ):
        return "Invalid data", 482

    if "ssh_key" not in data:
        data["ssh_key"] = ""

    return (
        ansible_helper.run_ansible(
            data["hosts"],
            data["playbook"],
            data["vault_password"],
            data["become_file"],
            ssh_key_file=data["ssh_key"],
        ),
        200,
    )


@app.route("/mac/<old_mac>/<new_mac>/")
@requires_auth_write
def update_mac(old_mac, new_mac):
    """Updates the old mac to the new mac"""
    mongo_client["labyrinth"]["hosts"].update_one(
        {"mac": old_mac}, {"$set": {"mac": new_mac}}
    )
    return "Success", 200


@app.route("/ip/<mac>/<new_ip>/")
@requires_auth_write
def update_ip(mac, new_ip):
    """Updates an IP for a given MAC address"""
    mongo_client["labyrinth"]["hosts"].update_one(
        {"mac": mac}, {"$set": {"ip": new_ip}}
    )
    return "Success", 200


# Dashboard


@app.route("/dashboard/<val>")
@app.route("/dashboard/")
@requires_auth_read
def dashboard(val="", report=False):
    """Dashboard"""
    # Get all the subnets

    rc = redis.Redis(host=os.environ.get("REDIS_HOST"))
    if str(val) == "1":
        cachedboard = rc.get("dashboard")
        if cachedboard:
            return rc.get("dashboard"), 200

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
            or_clause = []
            if "mac" in host and host["mac"] != "":
                or_clause.append({"tags.mac": host["mac"]})
            if "ip" in host and host["ip"] != "":
                or_clause.append({"tags.ip": host["ip"]})

            # Some networks have multiple hostnames that are the same...
            """
            if "host" in host and host["host"] != "":
                or_clause.append({"tags.host" : host["host"]})
            """

            if service.strip() == "open_ports" or service.strip() == "closed_ports":
                latest_metric = mongo_client["labyrinth"]["metrics"].find_one(
                    {
                        "name": "open_ports",
                        "$or": or_clause,
                    },
                    sort=[("timestamp", pymongo.DESCENDING)],
                )
                found_service = service

                result = mc.judge_port(latest_metric, service, host, stale_time=10000)
            else:
                latest_metric = mongo_client["labyrinth"]["metrics"].find_one(
                    {
                        "name": service,
                        "$or": or_clause,
                    },
                    sort=[("timestamp", pymongo.DESCENDING)],
                )
                found_service = mongo_client["labyrinth"]["services"].find_one(
                    {"name": service}
                )

                if latest_metric is None or found_service is None:
                    result = False
                else:
                    result = mc.judge(latest_metric, found_service)

            # Alerting section - this code is tested elsewhere
            if (
                report
                and (not result or result == -1)
                and ("monitor" in host and str(host["monitor"]).lower() == "true")
            ):  # pragma: no cover
                alert_name = "PROBLEM"
                metric_name = "None"
                if latest_metric is not None and "name" in latest_metric:
                    metric_name = latest_metric["name"]
                else:
                    metric_name = service

                host_name = host["host"] or host["ip"] or host["mac"]

                if result == -1:
                    summary = "No metric received in the window expected."
                else:
                    summary = "A service failed the metric check. | {} | {}".format(
                        json.dumps(latest_metric, default=str) or "",
                        json.dumps(found_service, default=str) or "",
                    )
                watcher.send_alert(alert_name, metric_name, host_name, summary=summary)

            service_results[service] = {"name": service, "state": result}
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
        for host in sorted(
            [x for x in subnet["hosts"] if "group" in x],
            key=lambda x: int(x["ip"].split(".")[-1]),
        ):
            if host["group"] not in groups:
                groups[host["group"]] = []
            groups[host["group"]].append(host)

        if "groups" not in subnet:
            subnet["groups"] = []

        for group in groups:
            subnet["groups"].append({"name": group, "hosts": groups[group]})
        del subnet["hosts"]

    if (
        not rc.get("dashboard_time")
        or time.time() - float(rc.get("dashboard_time")) > 5
    ):
        rc.set("dashboard", json.dumps(subnets, default=str))
        rc.set("dashboard_time", str(time.time()))
    return json.dumps(subnets, default=str), 200


# Metric


@app.route("/metrics/<int:count>", methods=["GET"])
@requires_auth_read
def last_metrics(count):
    """
    Lists the last <count> of metrics
    """
    return (
        json.dumps(
            [
                x
                for x in mongo_client["labyrinth"]["metrics"]
                .find({})
                .sort([("metrics.timestamp", pymongo.ASCENDING)])
            ][:count],
            default=str,
        ),
        200,
    )


@app.route("/metrics/<host>")
@app.route("/metrics/<host>/<service>")
@app.route("/metrics/<host>/<service>/<int:count>")
@requires_auth_read
def read_metrics(host, service="", count=10):
    """
    Returns the latest metrics for a given host
    """
    or_clause = {"$or": [{"tags.host": host}, {"tags.ip": host}, {"tags.mac": host}]}
    if service != "":
        or_clause["name"] = service

    found_host = mongo_client["labyrinth"]["hosts"].find_one(
        {"$or": [{"mac": host}, {"ip": host}]}
    )

    retval = [
        x
        for x in mongo_client["labyrinth"]["metrics"]
        .find(or_clause)
        .sort([("metrics.timestamp", pymongo.DESCENDING)])
    ]

    if service.strip() == "open_ports" or service.strip() == "closed_ports":
        for item in retval:
            item["judgement"] = mc.judge_port(
                item, service, found_host, stale_time=10000
            )
    else:
        found_service = mongo_client["labyrinth"]["services"].find_one(
            {"name": service}
        )
        for item in retval:
            if item is None or found_service is None:
                item["judgement"] = False
            else:
                item["judgement"] = mc.judge(item, found_service)

    return (
        json.dumps(retval[-1 * count :], default=str),
        200,
    )


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

    mongo_client["labyrinth"]["metrics"].create_index([("metrics.timestamp", -1)])

    if "metrics" not in data:  # pragma: no cover
        return "Invalid data", 421

    for item in data["metrics"]:
        mongo_client["labyrinth"]["metrics"].insert_one(item)

    return "Success", 200


if __name__ == "__main__":  # pragma: no cover

    if len(sys.argv) > 1 and sys.argv[1] == "watcher":
        unwrap(dashboard)(report=True)
    else:
        app.debug = True
        app.config["ENV"] = "development"
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7000)))
