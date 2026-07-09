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
import bson

import pymongo

import redis
import toml
import requests
import yaml

import metrics as mc
import watcher

import shutil
import services as svcs
import proxmox_helper
import proxmox_disk_check
import aws_helper

from common import auth
from common.test import unwrap
from flask import Flask, request, Response, send_file
from markupsafe import escape
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
from pid import PidFile

import uuid
from multiprocessing import Process


import ansible_runner
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
if os.getenv("GITHUB") or os.getenv("TESTBED"):
    mongo_client = pymongo.MongoClient(
        "mongodb://{}:{}@{}".format(
            os.environ.get("MONGO_USERNAME"),
            os.environ.get("MONGO_PASSWORD"),
            os.environ.get("MONGO_HOST"),
        )
    )

else:  # pragma: no cover
    mongo_client = pymongo.MongoClient(
        "mongodb+srv://{}:{}@{}".format(
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


@app.route("/upload/<file_type>/<override_token>", methods=["POST"])
@requires_auth_admin
def upload(file_type, override_token):  # pragma: no cover
    """
    Handles file upload
        - Two file_types: straight upload and form data upload
        - Form data upload comes from manual additions of vault files
    """
    if file_type not in valid_type:
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

    file_type = secure_filename(file_type)
    filename = secure_filename(filename)

    if file != "" and file.filename == "":
        return "No file selected", 409

    if not os.path.exists("/src/uploads"):
        os.makedirs("/src/uploads")

    if not os.path.exists("/src/uploads/{}".format(file_type)):
        os.mkdir("/src/uploads/{}".format(file_type))

    if data:
        data = data.replace("\r\n", "\n")
        with open("/tmp/{}".format(filename), "w") as f:
            f.write(data)

        if "{}.yml".format(filename.replace(".yml", "")) in os.listdir(
            "/src/uploads/become/"
        ):
            os.remove("/src/uploads/become/{}.yml".format(filename.replace(".yml", "")))

        if ansible_helper.check_file(filename, file_type):
            shutil.move(
                "/tmp/{}".format(filename),
                "/src/uploads/become/{}.yml".format(filename.replace(".yml", "")),
            )
            return escape(filename), 200
        os.remove("/tmp/{}".format(filename))
        return "File check failed", 522

    elif file:
        filename = secure_filename(file.filename)

        # file.save("/tmp/{}".format(filename))
        file_contents = file.read().decode("utf-8")
        file_contents = file_contents.replace("\r\n", "\n")
        with open(os.path.join("/tmp", filename), "w") as f:
            f.write(file_contents)

        check_results = ansible_helper.check_file(filename, file_type)
        if check_results:
            shutil.move(
                "/tmp/{}".format(filename),
                "/src/uploads/{}/{}".format(file_type, filename),
            )
        else:
            return f"File check failed: {check_results}", 521

    # Chmod
    chmod_filename = "/src/uploads/{}/{}".format(file_type, filename)
    os.chmod(chmod_filename, 0o600)
    return escape(filename), 200


@app.route("/uploads/<file_type>", methods=["GET"])
@requires_auth_admin
def list_uploads(file_type):
    """
    Lists all entries in an upload folder
    """
    file_type = secure_filename(file_type)
    if file_type in valid_type:
        fname = "/src/uploads/{}".format(file_type)
        if not os.path.exists(fname):
            os.mkdir(fname)
        return json.dumps(os.listdir(fname), default=str), 200
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


@app.route("/hosts/<tag>")
@requires_auth_read
def list_hosts_by_tag(tag):
    """Lists hosts that match a given tag or service name."""
    normalized_tag = str(tag).strip().lower()
    matching_hosts = []

    for host in mongo_client["labyrinth"]["hosts"].find({}):
        raw_tags = host.get("tags", "") or ""
        host_tags = [item.strip().lower() for item in raw_tags.split(",") if item.strip()]

        host_services = []
        for service in host.get("services", []) or []:
            if isinstance(service, dict):
                service_name = service.get("name") or service.get("display_name") or ""
            else:
                service_name = str(service)
            if service_name:
                host_services.append(service_name.strip().lower())

        if normalized_tag in host_tags or normalized_tag in host_services:
            matching_hosts.append(host)

    return json.dumps(matching_hosts, default=str), 200


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


@app.route("/host_group_rename/<ip>")
@app.route("/host_group_rename/<ip>/<group>/")
@requires_auth_write
def host_group_rename(ip, group=""):
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


# Tags (cross-subnet)


@app.route("/tags/")
@requires_auth_read
def list_tags():
    """
    Lists all unique tags across all hosts (cross-subnet)
    """
    all_tags = set()
    for host in mongo_client["labyrinth"]["hosts"].find({}):
        raw = host.get("tags", "")
        if raw:
            for tag in raw.split(","):
                tag = tag.strip()
                if tag:
                    all_tags.add(tag)
    return json.dumps(sorted(all_tags), default=str), 200


@app.route("/tags/<tag>")
@requires_auth_read
def list_tag_members(tag):
    """
    Lists IPs of all hosts that have a given tag (cross-subnet)
    """
    ips = []
    for host in mongo_client["labyrinth"]["hosts"].find({}):
        raw = host.get("tags", "")
        if raw:
            host_tags = [t.strip() for t in raw.split(",")]
            if tag in host_tags:
                ips.append(host["ip"])
    return json.dumps(ips, default=str), 200


@app.route("/host_tags/<ip>/")
@app.route("/host_tags/<ip>/<tags>/")
@requires_auth_write
def update_host_tags(ip, tags=""):
    """
    Updates the tags for a given host (by IP). Tags is a comma-delimited string.
    """
    found = mongo_client["labyrinth"]["hosts"].find_one({"ip": ip})
    if not found:
        return "Not found", 498
    mongo_client["labyrinth"]["hosts"].update_many({"ip": ip}, {"$set": {"tags": tags}})
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
                [
                    x["display_name"]
                    for x in mongo_client["labyrinth"]["services"].find({})
                    if "display_name" in x
                ],
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
            [
                x
                for x in mongo_client["labyrinth"]["services"].find(
                    {"display_name": name}
                )
            ],
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

    if "_id" in data:
        del data["_id"]

    if "display_name" not in data:
        data["display_name"] = ""

    if [
        x
        for x in mongo_client["labyrinth"]["services"].find(
            {"display_name": data["display_name"]}
        )
    ]:
        mongo_client["labyrinth"]["services"].delete_one(
            {"display_name": data["display_name"]}
        )

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
    name = secure_filename(name)
    # Delete Service
    mongo_client["labyrinth"]["services"].delete_one({"display_name": name})

    # Check for hosts that had the service
    mongo_client["labyrinth"]["hosts"].update_many(
        {"services": {"$in": [name]}}, {"$pull": {"services": name}}
    )
    # Check if snippet exists
    if name in os.listdir("/src/snippets/"):
        os.remove("/src/snippets/{}".format(name))

    return "Success", 200


# Redis
@app.route("/redis/")
@requires_auth_read
def read_redis():
    """Returns the output of the redis run"""
    a = redis.Redis(host=os.environ.get("REDIS_HOST"))

    # List all the redis keys of the output_[subnet name]
    keys = a.keys(pattern="output-*")

    # Get each one, then send it out properly
    retval = {}
    for key in keys:
        retval[key.decode("utf-8").split("-")[1]] = a.get(key).decode("utf-8")

    return json.dumps(retval, default=str), 200


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
    host = secure_filename(host)
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
    fname = secure_filename(fname)
    return svcs.run(fname, testing == 1), 200


# Load TOML file
@app.route("/load_service/<name>")
@app.route("/load_service/<name>/<file_format>")
@requires_auth_admin
def load_service(name, file_format="json"):
    """
    Loads in a TOML service file
    """
    name = secure_filename(name)
    return svcs.load(name, file_format), 200


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
    headers = {"Content-Type": "application/json"}

    return (
        json.dumps(requests.get(url, auth=("admin", password), headers=headers).json()),
        200,
    )


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

    url = "http://alertmanager:9093/api/v2/alerts"
    password = open("/alertmanager/pass").read()

    del parsed_data["startsAt"]
    parsed_data["status"] = "resolved"
    parsed_data["endsAt"] = "2021-08-03T14:34:41-05:00"

    headers = {"Content-Type": "application/json"}

    retval = requests.post(
        url, data=json.dumps([parsed_data]), auth=("admin", password), headers=headers
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

    headers = {"Content-Type": "application/json"}

    retval = requests.post(url, auth=("admin", password), headers=headers)
    return retval.text, retval.status_code


@app.route("/alertmanager/test")
@requires_auth_admin
def alertmanager_test():  # pragma: no cover
    """
    Sends out a test email from alertmanager
    """
    a = watcher.send_alert(
        "Test Email - {}".format(time.time()), "Service", "Something", summary="Summary"
    )
    return a.text, a.status_code


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


@app.route("/settings/restart")
@app.route("/settings/restart/<int:code>")
@requires_auth_admin
def restart(code=0):  # pragma: no cover
    """
    Restarts either the process or the docker
    """
    if int(code) == 0:
        print("Exiting 0")
        sys.exit(0)
    elif int(code) == 4:
        print("Exiting 4")
        sys.exit(4)
    else:
        return "Invalid exit code", 400


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


@app.route("/icon/", methods=["POST"])
@requires_auth_admin
def upload_icon(override=""):  # pragma: no cover
    """
    Upload an icon
    """
    if override == "":  # pragma: no cover
        file = request.files["file"]
        filename = secure_filename(file.filename)
        file.save("/public/icons/{}".format(filename))
    else:
        shutil.move(override, "/public/icons/{}".format(override.split("/")[-1]))

    return "Success", 200


# Theme
@app.route("/themes/")
@requires_auth_read
def list_themes():
    """
    Lists themes
    """
    defaults_file = "/src/common/default_colors.json"
    # Check if the defaults exist - create if not

    themes = list(mongo_client["labyrinth"]["themes"].find({}))
    if len(themes) < 3:
        with open(defaults_file) as f:
            defaults = json.load(f)
            for item in defaults:
                mongo_client["labyrinth"]["themes"].insert_one(item)

    #  Return all of them
    return (
        json.dumps(
            sorted(
                list(mongo_client["labyrinth"]["themes"].find({})),
                key=lambda x: x["name"],
            ),
            default=str,
        ),
        200,
    )


@app.route("/themes/", methods=["POST"])
@requires_auth_admin
def create_edit_theme(data=""):
    """
    Creates/edits a theme
    """
    if data == "":
        data = json.loads(request.form.get("data"))

    # Delete any with the same name
    if "name" not in data:
        return "Invalid data", 485

    mongo_client["labyrinth"]["themes"].delete_one({"name": data["name"]})

    mongo_client["labyrinth"]["themes"].insert_one(data)
    return "Success", 200


@app.route("/themes/<theme_name>", methods=["DELETE"])
@requires_auth_admin
def delete_theme(theme_name):
    """
    Deletes a theme
    """
    mongo_client["labyrinth"]["themes"].delete_one({"name": theme_name})
    return "Success", 200


# Utilities


@app.route("/find_ip/")
@app.route("/find_ip/<name>")
@requires_auth_admin
def find_ip(name=""):
    """
    Returns the IP for the docker container
    """
    if os.environ.get("PRODUCTION") == 1 and name == "sampleclient":
        return ""
    if name is None or name == "":
        return socket.gethostbyname(socket.gethostname()), 200
    else:
        return socket.gethostbyname(name), 200


@app.route("/list_directory/<file_type>")
@requires_auth_admin
def list_directory(file_type):
    """
    Lists directory
    """
    file_type = secure_filename(file_type)

    if file_type not in valid_type:  # pragma: no cover
        return "Invalid type", 446

    if not os.path.exists("/src/uploads/{}".format(file_type)):  # pragma: no cover
        return "No folder", 447

    return json.dumps(os.listdir("/src/uploads/{}".format(file_type))), 200


@app.route("/new_ansible_file/<fname>")
@requires_auth_admin
def new_ansible_file(fname):
    """
    Creates a new ansible file
    """
    fname = secure_filename(fname)
    filename = "/src/uploads/ansible/{}.yml".format(fname.replace(".yml", ""))
    if os.path.exists(filename):
        return "File already exists", 407
    with open(filename, "w") as f:
        f.write("")
    return escape(filename), 200


@app.route("/get_ansible_file/<fname>")
@requires_auth_admin
def get_ansible_file(fname):
    """
    Returns the given ansible file
    """
    fname = secure_filename(fname)
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


def run_ansible_background(job_id, data):
    """Run Ansible in the background and store results in Redis."""
    redis_client = redis.Redis(host=os.environ.get("REDIS_HOST"))
    RUN_DIR, playbook = ansible_helper.run_ansible(
        data["hosts"],
        data["playbook"],
        data["vault_password"],
        data["become_file"],
        ssh_key_file=data.get("ssh_key", ""),
    )

    redis_client.hset(job_id, "status", "running")

    try:
        thread, runner = ansible_runner.run_async(
            private_data_dir=RUN_DIR,
            playbook=f"{playbook}.yml",
            cmdline="-vvvvv --vault-password-file ../vault.pass",
            quiet=True,
        )

        results = []
        while thread.is_alive():
            for event in runner.events:
                stdout = event.get("stdout", "")
                if stdout:
                    results.append(stdout)
                    redis_client.rpush(f"{job_id}_log", stdout)
            time.sleep(0.1)

        redis_client.hset(job_id, "status", "completed")
        redis_client.hset(job_id, "results", json.dumps(results))

    except Exception as e:
        redis_client.hset(job_id, "status", "error")
        redis_client.hset(job_id, "error", str(e))

    finally:
        if "vault.pass" in os.listdir(RUN_DIR):
            os.remove(f"{RUN_DIR}/vault.pass")
        if os.path.exists("/vault.pass"):
            os.remove("/vault.pass")
        shutil.rmtree(RUN_DIR)


@app.route("/ansible_runner/", methods=["POST"])
@requires_auth_admin
def run_ansible_endpoint(inp_data=""):
    redis_client = redis.Redis(host=os.environ.get("REDIS_HOST"))
    if inp_data:
        data = inp_data
    else:  # pragma: no cover
        data = request.form.get("data")
        if not data:
            return "Invalid data", 481

    data = json.loads(data)
    required_keys = ["hosts", "playbook", "vault_password", "become_file"]
    if not all(key in data for key in required_keys):
        return "Invalid data", 482

    job_id = f"ansible_job_{uuid.uuid4()}"
    redis_client.hset(job_id, "status", "queued")

    # Start the process
    process = Process(target=run_ansible_background, args=(job_id, data))
    process.start()

    return {"job_id": job_id, "status": "started"}, 200


@app.route("/ansible_status/<job_id>", methods=["GET"])
@app.route("/ansible_status/<job_id>/", methods=["GET"])
@requires_auth_admin
def get_ansible_status(job_id):
    redis_client = redis.Redis(host=os.environ.get("REDIS_HOST"))
    status = redis_client.hget(job_id, "status")
    if not status:
        return {"error": "Job not found"}, 404

    logs = redis_client.lrange(f"{job_id}_log", 0, -1)
    results = redis_client.hget(job_id, "results")

    return {
        "job_id": str(escape(job_id)),
        "status": status.decode("utf-8"),
        "logs": [log.decode("utf-8") for log in logs],
        "results": json.loads(results.decode("utf-8")) if results else None,
    }, 200


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


def index_helper():  # pragma: no cover
    """
    Helps with ensuring indexes are created
    """

    # mongo_client["labyrinth"]["metrics"].create_index(
    #    [("timestamp", pymongo.DESCENDING)]
    # )
    # mongo_client["labyrinth"]["metrics"].create_index("name")
    # mongo_client["labyrinth"]["metrics"].create_index("tags")
    mongo_client["labyrinth"]["metrics-latest"].create_index("tags")

    """
    mongo_client["labyrinth"]["metrics"].create_index(
        [
            ("tags.ip", pymongo.DESCENDING),
            ("tags.host", pymongo.DESCENDING),
            ("tags.mac", pymongo.DESCENDING),
        ]
    )
    """

    mongo_client["labyrinth"]["services"].create_index("name")
    mongo_client["labyrinth"]["services"].create_index("display_name")
    mongo_client["labyrinth"]["hosts"].create_index("ip")
    mongo_client["labyrinth"]["hosts"].create_index("mac")
    mongo_client["labyrinth"]["hosts"].create_index("subnet")
    mongo_client["labyrinth"]["settings"].create_index("name")
    mongo_client["labyrinth"]["proxmox_clusters"].create_index("name")
    mongo_client["labyrinth"]["aws_accounts"].create_index("name")
    # mongo_client["labyrinth"]["metrics"].create_index([("timestamp", -1)])

    # Make Metrics Latest expire after a certain time period
    mongo_client["labyrinth"]["metrics-latest"].create_index(
        [("timestamp", 1)], expireAfterSeconds=36000
    )


@app.route("/dashboard/<val>")
@app.route("/dashboard/")
@requires_auth_read
def dashboard(val="", report=False, flapping_delay=1300):
    """
    Dashboard
        - This is also called to judge and send out alerts (flag `report`)
        - `flapping_delay` is how long a metric must be failing before a report is sent out (in seconds)
    """

    # Sorting helper for groups
    def group_sorting_helper(x):
        """
        Sorting helper for groups
            - This fixes unicode groups (like a star)
        """
        try:
            val = ord(x[0].lower())
            if val < 10000:
                val = val + 200000
            return val
        except IndexError:
            return 0

    # Get all the subnets

    rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
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

    # Get all services
    all_services = list(mongo_client["labyrinth"]["services"].find({}))

    # Get latest metrics

    latest_metrics = {}
    for item in mongo_client["labyrinth"]["metrics-latest"].find(
        {}, sort=[("_id", pymongo.ASCENDING)]
    ):
        if "name" in item:
            if item["name"] not in latest_metrics:
                latest_metrics[item["name"]] = []
            latest_metrics[item["name"]].append(item)

    def find_metric(service_name, host, tag_name="", tag_value=""):
        """
        Finds a metric from the latest metrics list
        """
        processed = service_name.strip()
        if processed not in latest_metrics:
            return None
        found = None
        for item in latest_metrics[processed]:
            mac_clause = (
                "tags" in item
                and "mac" in item["tags"]
                and "mac" in host
                and item["tags"]["mac"] == host["mac"]
            )
            ip_clause = (
                "tags" in item
                and "ip" in item["tags"]
                and "ip" in host
                and item["tags"]["ip"] == host["ip"]
            )

            if tag_name:
                additional_tag_clause = (
                    "tags" in item
                    and tag_name in item["tags"]
                    and item["tags"][tag_name] == tag_value
                )
            else:
                additional_tag_clause = True

            if (mac_clause or ip_clause) and additional_tag_clause:
                if found and "timestamp" in found and type(found["timestamp"]) == float:
                    found["timestamp"] = datetime.datetime.fromtimestamp(
                        found["timestamp"]
                    )
                if item and "timestamp" in item and type(item["timestamp"]) == float:
                    item["timestamp"] = datetime.datetime.fromtimestamp(
                        item["timestamp"]
                    )

                if found is None or (
                    "timestamp" in item and item["timestamp"] > found["timestamp"]
                ):
                    found = item

        return found

    def find_service(name):
        """
        Returns the given service
        """
        for item in all_services:
            if item["display_name"] == name:
                return item
        return None

    # Get the hosts latest metrics for states
    for host in [x for x in hosts if "services" in x]:
        service_results = {}
        for service in host["services"]:
            or_clause = []

            if service.strip() == "open_ports" or service.strip() == "closed_ports":
                latest_metric = find_metric("open_ports", host)
                found_service = service

                result = mc.judge_port(latest_metric, service, host, stale_time=10000)
            else:
                found_service = find_service(service)

                if found_service and "display_name" in found_service:
                    if (
                        "tag_name" in found_service
                        and found_service["tag_name"]
                        and "tag_value" in found_service
                    ):
                        latest_metric = find_metric(
                            found_service["name"],
                            host,
                            found_service["tag_name"],
                            found_service["tag_value"],
                        )
                    else:
                        latest_metric = find_metric(found_service["name"], host)

                    if not latest_metric:
                        result = False
                    else:
                        result = mc.judge(latest_metric, found_service)
                else:
                    result = False

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

                key_name = f"{alert_name}{metric_name}{host_name}".replace(" ", "")
                found_key = rc.get(key_name)
                if found_key and time.time() - float(found_key) < flapping_delay:
                    # Handle found_service severity
                    severity = "error"
                    if "service_level" in host and host["service_level"] == "warning":
                        severity = "warning"
                    elif "service_levels" in host:
                        for item in host["service_levels"]:
                            # Check for open_ports and closed_ports, which are special
                            if (
                                item
                                and "service" in item
                                and found_service
                                and item["service"] == found_service
                                and "level" in item
                                and item["level"] == "warning"
                            ):
                                severity = "warning"
                            if (
                                item
                                and "service" in item
                                and found_service
                                and "display_name" in found_service
                                and item["service"] == found_service["display_name"]
                                and "level" in item
                                and item["level"] == "warning"
                            ):
                                severity = "warning"
                                break
                    watcher.send_alert(
                        alert_name,
                        metric_name,
                        host_name,
                        summary=summary,
                        severity=severity,
                    )
                rc.set(key_name, time.time())

            service_results[service] = {
                "name": service,
                "state": result,
                "found_service": found_service,
                "latest_metric": latest_metric,
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
        for host in sorted(
            [x for x in subnet["hosts"] if "group" in x],
            key=lambda x: int(x["ip"].split(".")[-1]),
        ):
            if host["group"] not in groups:
                groups[host["group"]] = []
            groups[host["group"]].append(host)

        if "groups" not in subnet:
            subnet["groups"] = []

        for group in sorted(groups.keys(), key=group_sorting_helper):
            subnet["groups"].append({"name": group, "hosts": groups[group]})
        del subnet["hosts"]

    if (
        not rc.get("dashboard_time")
        or time.time() - float(rc.get("dashboard_time")) > 5
    ):
        rc.set("dashboard", json.dumps(subnets, default=str))
        rc.set("dashboard_time", str(time.time()))
    return json.dumps(subnets, default=str), 200


## Custom Dashboards
@app.route("/custom_dashboards/")
@app.route("/custom_dashboards/<dashboard>")
@requires_auth_read
def list_custom_dashboards(dashboard=""):
    """
    Lists Custom Dashboards or single dashboard
    """
    criteria = {}
    if dashboard:
        criteria = {"name": dashboard}
    a = list(mongo_client["labyrinth"]["dashboards"].find(criteria))
    if not a:
        return "No Dashboards created yet.", 404
    return json.dumps(a, default=str), 200


@app.route("/custom_dashboard/<dashboard>", methods=["POST"])
@requires_auth_write
def create_edit_custom_dashboard(dashboard, data=""):
    """
    Creates/Edits a Custom Dashboard
    """
    if data == "":
        data = json.loads(request.form.get("data"))

    mongo_client["labyrinth"]["dashboards"].delete_many({"name": dashboard})

    data["name"] = dashboard

    mongo_client["labyrinth"]["dashboards"].insert_one(data)
    return "Success", 200


@app.route("/custom_dashboard/<dashboard>", methods=["DELETE"])
@requires_auth_write
def delete_custom_dashboard(dashboard):
    """
    Deletes a custom dashboard
    """
    mongo_client["labyrinth"]["dashboards"].delete_many({"name": dashboard})
    return "Success", 200


### Custom Dashboards Images
@app.route("/custom_dashboard_images/", methods=["GET"])
@requires_auth_read
def custom_dashboard_list_images():
    """
    Lists available images for Custom Dashboards
    """
    if os.path.exists("/src/uploads/images"):
        return json.dumps(os.listdir("/src/uploads/images"), default=str), 200

    return json.dumps([]), 200


@app.route("/custom_dashboard_images/<override_token>/<filename>")
def custom_dashboard_return_image(override_token, filename):
    """
    Returns a specific image file
    """
    filename = secure_filename(filename)
    if os.path.exists("/src/uploads/images") and filename in os.listdir(
        "/src/uploads/images"
    ):
        return send_file(os.path.join("/src/uploads/images/", filename))
    return "Not found", 404


@app.route("/custom_dashboard_images/<dashboard_image>", methods=["DELETE"])
@requires_auth_write
def custom_dashboard_delete_image(dashboard_image):
    """
    Deletes a Custom Dashboard Image
    """
    dashboard_image = secure_filename(dashboard_image)
    dir_list = os.listdir("/src/uploads/images")
    if dashboard_image not in dir_list:
        return "Not Found", 404

    if os.path.exists("/src/uploads/images/{}".format(dashboard_image)):
        os.remove("/src/uploads/images/{}".format(dashboard_image))

    return "Success", 200


@app.route("/custom_dashboard_images/", methods=["POST"])
@requires_auth_write
def custom_dashboard_image_upload(override=""):
    """
    Custom Dashboard Image Upload
    """
    if override == "":  # pragma: no cover
        if "file" not in request.files:
            return "No file included", 407
        file = request.files["file"]

    if not os.path.exists("/src/uploads"):
        os.makedirs("/src/uploads")

    if not os.path.exists("/src/uploads/images"):
        os.makedirs("/src/uploads/images")

    if override:
        filename = override
    elif file:  # pragma: no cover
        filename = secure_filename(file.filename)
        file.save("/tmp/{}".format(filename))

    try:
        Image.open("/tmp/{}".format(filename)).verify()
    except Exception:
        return "Invalid file", 484

    shutil.move("/tmp/{}".format(filename), "/src/uploads/images/{}".format(filename))
    return "Success", 200


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
                for x in mongo_client["labyrinth"]["metrics-latest"]
                .find({})
                .sort([("metrics-latest.timestamp", pymongo.ASCENDING)])
            ],
            default=str,
        ),
        200,
    )


@app.route("/metrics/<host>")
@app.route("/metrics/<host>/<service>")
@app.route("/metrics/<host>/<service>/<int:count>")
@app.route("/metrics/<host>/<service>/<option>")
@requires_auth_read
def read_metrics(host, service="", count=100, option=""):
    """
    Returns the latest metrics for a given host
    """
    or_clause = {"$or": [{"tags.host": host}, {"tags.ip": host}, {"tags.mac": host}]}

    found_host = mongo_client["labyrinth"]["hosts"].find_one(
        {"$or": [{"mac": host}, {"ip": host}]}
    )

    found_service = mongo_client["labyrinth"]["services"].find_one(
        {"display_name": service}
    )

    if service != "" and found_service:
        or_clause["tags.labyrinth_name"] = found_service["name"]
        if (
            "tag_name" in found_service
            and found_service["tag_name"]
            and "tag_value" in found_service
        ):
            or_clause["tags.{}".format(found_service["tag_name"])] = found_service[
                "tag_value"
            ]
    elif service != "":
        or_clause["tags.labyrinth_name"] = service

    print(or_clause)

    table = "metrics"
    if option == "latest":
        table = "metrics-latest"

    retval = [
        x
        for x in mongo_client["labyrinth"][table]
        .find(or_clause)
        .sort("_id", -1)
        .limit(count)
    ]

    if service.strip() == "open_ports" or service.strip() == "closed_ports":
        for item in retval:
            item["judgement"] = mc.judge_port(
                item, service, found_host, stale_time=10000
            )
            item["judgement_debug"] = {
                "item": json.dumps(item, default=str),
                "service": service,
                "found_host": found_host,
            }
    else:
        for item in retval:
            if item is None or found_service is None:
                item["judgement"] = False
            else:
                item["judgement"] = mc.judge(item, found_service)

    return (
        json.dumps(retval[::-1], default=str),
        200,
    )


@app.route("/metrics/<metric_id>", methods=["DELETE"])
@requires_auth_write
def delete_metric(metric_id):
    """
    Deletes a metric id
    """
    object_id = bson.ObjectId(metric_id)
    mongo_client["labyrinth"]["metrics-latest"].delete_one({"_id": object_id})
    return "Success", 200


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

    if "metrics" not in data:  # pragma: no cover
        return "Invalid data", 421

    for item in data["metrics"]:

        if "tags" in item and "name" in item:

            a = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")

            name = json.dumps({"name": item["name"], "tags": item["tags"]}, default=str)
            a.set(f"METRIC-{name}", json.dumps(item, default=str))
            a.expire(f"METRIC-{name}", 120)

    return "Success", 200


@app.route("/bulk_insert/", methods=["GET"])
@requires_auth_write
def bulk_insert():
    """
    Bulk insert of the redis entries into mongo
        - Can be called manually or periodically
    """
    metrics_latest_updates = []
    metrics_updates = []

    a = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")

    # Find all metrics from Redis
    metrics = a.keys(pattern="METRIC-*")
    for metric in metrics:
        print("Inserting", metric)
        item = json.loads(a.get(metric))
        print("Item:", item)
        last_time = a.get("last_metric_{}".format(item["tags"]["ip"]))

        if "tags" not in item or "name" not in item:
            continue

        if "timestamp" in item:
            try:
                # item["timestamp"] = datetime.datetime.fromtimestamp(item["timestamp"])
                item["timestamp"] = datetime.datetime.now()
            except Exception:
                print("Problem with timestamp - ", sys.exc_info())

        if type(item["tags"]) == type({}):
            item["tags"]["labyrinth_name"] = item["name"]
            item["tags"]["agent_name"] = socket.gethostname()

        try:
            if last_time and (time.time() - float(last_time)) <= 15:
                pass
            else:
                """
                mongo_client["labyrinth"]["metrics-latest"].replace_one(
                    {"tags": item["tags"], "name": item["name"]}, item, upsert=True
                )
                """
                metrics_latest_updates.append(
                    pymongo.ReplaceOne(
                        {"tags": item["tags"], "name": item["name"]}, item, upsert=True
                    )
                )
        except Exception:
            raise Exception(item)

        if last_time and (time.time() - float(last_time)) <= 120:
            pass
        else:

            """
            mongo_client["labyrinth"]["metrics"].insert_one(item)
            """
            metrics_updates.append(pymongo.InsertOne(item))

            a.set("last_metric_{}".format(item["tags"]["ip"]), time.time())

    # Bulk writes
    if metrics_latest_updates:
        mongo_client["labyrinth"]["metrics-latest"].bulk_write(metrics_latest_updates)

    if metrics_updates:
        mongo_client["labyrinth"]["metrics"].bulk_write(metrics_updates)

    return len(metrics), 200


# Disk Space Monitoring
def _normalize_match_string(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _candidate_host_names(host):
    candidates = set()
    for key in ["host", "name"]:
        value = _normalize_match_string(host.get(key))
        if not value:
            continue
        candidates.add(value)
        if "." in value:
            candidates.add(value.split(".")[0])
    return candidates


def _candidate_instance_names(instance):
    candidates = set()
    tag_name = ((instance.get("tags") or {}).get("Name"))
    for value in [
        instance.get("instance_id"),
        instance.get("name"),
        instance.get("private_dns_name"),
        instance.get("public_dns_name"),
        tag_name,
    ]:
        normalized = _normalize_match_string(value)
        if not normalized:
            continue
        candidates.add(normalized)
        if "." in normalized:
            candidates.add(normalized.split(".")[0])
    return candidates


def _truthy_monitor_value(value):
    return _normalize_match_string(value) in ["true", "1", "yes", "on"]


def _build_labyrinth_host_match(instance, host):
    reasons = []
    host_ip = _normalize_match_string(host.get("ip"))
    instance_ips = {
        _normalize_match_string(instance.get("private_ip")),
        _normalize_match_string(instance.get("public_ip")),
    }
    instance_ips.discard("")

    if host_ip and host_ip in instance_ips:
        reasons.append("ip")

    host_names = _candidate_host_names(host)
    instance_names = _candidate_instance_names(instance)
    if host_names and instance_names and host_names.intersection(instance_names):
        reasons.append("hostname")

    if not reasons:
        return None

    services = host.get("services") or []
    return {
        "ip": host.get("ip"),
        "mac": host.get("mac"),
        "host": host.get("host") or host.get("name"),
        "group": host.get("group"),
        "tags": host.get("tags", ""),
        "monitor": host.get("monitor"),
        "service_count": len(services),
        "services": services,
        "match_reasons": reasons,
    }


def _enrich_aws_instances_with_matches(instances):
    hosts = list(mongo_client["labyrinth"]["hosts"].find({}))
    enriched_instances = []

    for instance in instances:
        matches = []
        for host in hosts:
            match = _build_labyrinth_host_match(instance, host)
            if match:
                matches.append(match)

        monitoring_enabled = any(
            _truthy_monitor_value(match.get("monitor")) or match.get("service_count", 0) > 0
            for match in matches
        )

        enriched = dict(instance)
        enriched["labyrinth_matches"] = matches
        enriched["match_count"] = len(matches)
        enriched["matched"] = len(matches) > 0
        enriched["monitoring_enabled"] = monitoring_enabled
        enriched_instances.append(enriched)

    return enriched_instances


@app.route("/disk-space/proxmox")
@requires_auth_read
def get_proxmox_disk_space():
    """
    Get disk space data from all configured Proxmox clusters
    """
    try:
        clusters = list(mongo_client["labyrinth"]["proxmox_clusters"].find({}))
        redis_client = proxmox_helper.get_redis_client()

        result = {
            "proxmox_hosts": []
        }

        for cluster in clusters:
            data = proxmox_helper.get_proxmox_disk_data_cached(
                cluster,
                redis_client=redis_client,
            )
            result["proxmox_hosts"].append(data)

        return json.dumps(result, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/disk-space/manual")
@requires_auth_read
def get_manual_disk_space():
    """
    Get disk space data from manually configured hosts
    """
    try:
        manual_hosts = []
        for setting in mongo_client["labyrinth"]["settings"].find(
            {"name": {"$regex": "^manual_disk_host_"}}
        ):
            host_config = setting.get("value")
            if isinstance(host_config, str):
                host_config = json.loads(host_config)
            host_config.setdefault("id", setting["name"].replace("manual_disk_host_", ""))
            manual_hosts.append(host_config)

        result = {
            "manual_hosts": manual_hosts
        }

        return json.dumps(result, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/disk-space/manual", methods=["POST"])
@app.route("/disk-space/manual/", methods=["POST"])
@requires_auth_admin
def add_manual_disk_host():
    """
    Add a manually configured host for disk space monitoring
    Expected JSON: {"name": "host_name", "ip": "ip_address", "type": "ec2|oraclevbox|generic"}
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            data = {
                "name": request.form.get("name"),
                "ip": request.form.get("ip"),
                "type": request.form.get("type"),
                "description": request.form.get("description", ""),
            }

        if data is None:
            return json.dumps({"error": "Invalid JSON body"}), 400

        required_fields = ["name", "ip", "type"]

        if not all(data.get(field) for field in required_fields):
            return json.dumps({"error": "Missing required fields"}), 400

        # Generate unique ID
        host_id = str(uuid.uuid4())
        setting_name = f"manual_disk_host_{host_id}"

        stored_data = {
            "id": host_id,
            "name": data["name"],
            "ip": data["ip"],
            "type": data["type"],
            "description": data.get("description", ""),
            "created": datetime.datetime.utcnow().isoformat(),
            "updated": datetime.datetime.utcnow().isoformat(),
        }

        mongo_client["labyrinth"]["settings"].insert_one({
            "name": setting_name,
            "value": json.dumps(stored_data)
        })

        return json.dumps({"id": host_id, "status": "created"}), 201
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/disk-space/manual/<host_id>", methods=["DELETE"])
@requires_auth_admin
def delete_manual_disk_host(host_id):
    """
    Delete a manually configured disk space monitoring host
    """
    try:
        setting_name = f"manual_disk_host_{host_id}"
        result = mongo_client["labyrinth"]["settings"].delete_one(
            {"name": setting_name}
        )
        
        if result.deleted_count == 0:
            return json.dumps({"error": "Host not found"}), 404

        return json.dumps({"status": "deleted"}), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/disk-space/settings", methods=["GET"])
@requires_auth_read
def get_disk_space_settings():
    """
    Get disk space monitoring settings (clusters, tags, alert threshold/recipients)
    """
    try:
        tag_setting = mongo_client["labyrinth"]["settings"].find_one(
            {"name": "proxmox_tag"}
        )
        threshold_setting = mongo_client["labyrinth"]["settings"].find_one(
            {"name": "disk_space_alert_threshold"}
        )
        recipients_setting = mongo_client["labyrinth"]["settings"].find_one(
            {"name": "disk_space_alert_recipients"}
        )

        raw_recipients = recipients_setting.get("value") if recipients_setting else ""
        if isinstance(raw_recipients, str):
            recipients_list = [r.strip() for r in raw_recipients.split(",") if r.strip()]
        elif isinstance(raw_recipients, list):
            recipients_list = raw_recipients
        else:
            recipients_list = []

        threshold_value = threshold_setting.get("value") if threshold_setting else None
        try:
            threshold_percent = int(threshold_value) if threshold_value not in (None, "") else 80
        except (TypeError, ValueError):
            threshold_percent = 80

        result = {
            "proxmox_tag": tag_setting.get("value") if tag_setting else "Proxmox",
            "disk_space_alert_threshold": threshold_percent,
            "disk_space_alert_recipients": recipients_list,
            "clusters": [],
            "unconfigured_proxmox_hosts": []
        }

        # Get all clusters
        clusters = list(mongo_client["labyrinth"]["proxmox_clusters"].find({}))
        for cluster in clusters:
            cluster.pop("token_secret", None)
            cluster["_id"] = str(cluster["_id"])
            result["clusters"].append(cluster)

        # Get list of Proxmox-tagged hosts without cluster assignment
        proxmox_tag = result["proxmox_tag"]
        for host in mongo_client["labyrinth"]["hosts"].find({}):
            raw_tags = host.get("tags", "")
            if raw_tags:
                host_tags = [t.strip() for t in raw_tags.split(",")]
                if proxmox_tag in host_tags and not (host.get("proxmox_cluster") or "").strip():
                    result["unconfigured_proxmox_hosts"].append({
                        "mac": host.get("mac"),
                        "ip": host.get("ip"),
                        "name": host.get("host") or host.get("name"),
                    })

        return json.dumps(result, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/disk-space/test-email", methods=["POST"])
@app.route("/disk-space/test-email/", methods=["POST"])
@requires_auth_admin
def send_disk_space_test_email():
    """
    Manually trigger a disk space alert test email.

    Expected JSON body: {
        "mode": "simple" | "full",   # default "simple"
        "recipients": ["a@example.com"]  # optional, overrides saved settings
    }

    - "simple": sends a minimal message confirming SMTP is configured
      correctly, without querying Proxmox.
    - "full": queries live/cached Proxmox cluster data using the saved (or
      overridden) alert threshold and sends the real alert template,
      always sending even if zero disks are currently over threshold, so
      admins can preview formatting and confirm delivery.
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            try:
                data = json.loads(request.get_data(as_text=True)) if request.get_data(as_text=True) else {}
            except (ValueError, json.JSONDecodeError):
                return json.dumps({"error": "Invalid JSON body"}), 400

        mode = (data.get("mode") or "simple").lower()
        if mode not in ("simple", "full"):
            return json.dumps({"error": "mode must be 'simple' or 'full'"}), 400

        recipients = data.get("recipients")
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",") if r.strip()]

        if not recipients:
            # Fall back to saved recipients (same settings the alert cron uses)
            recipients_setting = mongo_client["labyrinth"]["settings"].find_one(
                {"name": "disk_space_alert_recipients"}
            )
            raw_recipients = recipients_setting.get("value") if recipients_setting else ""
            if isinstance(raw_recipients, str):
                recipients = [r.strip() for r in raw_recipients.split(",") if r.strip()]
            elif isinstance(raw_recipients, list):
                recipients = raw_recipients
            else:
                recipients = []

        if not recipients:
            return json.dumps({
                "error": "No recipients configured. Add recipients first or include them in the request."
            }), 400

        if mode == "full":
            result = proxmox_disk_check.send_full_test_email(
                recipients, db=mongo_client, redis_client=proxmox_helper.get_redis_client()
            )
            return json.dumps({
                "status": "sent",
                "mode": "full",
                "recipients": recipients,
                **result,
            }), 200

        proxmox_disk_check.send_simple_test_email(recipients)
        return json.dumps({
            "status": "sent",
            "mode": "simple",
            "recipients": recipients,
        }), 200
    except ValueError as e:
        return json.dumps({"error": str(e)}), 400
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/proxmox-clusters")
@app.route("/proxmox-clusters/", methods=["GET"])
@requires_auth_read
def list_proxmox_clusters():
    """
    List all Proxmox clusters
    """
    try:
        clusters = list(mongo_client["labyrinth"]["proxmox_clusters"].find({}))
        # Remove sensitive data from response
        for cluster in clusters:
            cluster.pop("token_secret", None)
        return json.dumps(clusters, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/proxmox-clusters", methods=["POST"])
@app.route("/proxmox-clusters/", methods=["POST"])
@requires_auth_admin
def create_proxmox_cluster():
    """
    Create a new Proxmox cluster configuration
    Expected JSON: {
        "name": "cluster-1",
        "host": "10.1.1.1",
        "user": "root@pam",
        "token_id": "token-id",
        "token_secret": "token-secret",
        "verify_ssl": false
    }
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            # Try to parse raw request body as JSON
            try:
                data = json.loads(request.get_data(as_text=True))
            except (ValueError, json.JSONDecodeError):
                return json.dumps({"error": "Invalid JSON body"}), 400

        required_fields = ["name", "host", "user", "token_id", "token_secret"]
        if not all(data.get(field) for field in required_fields):
            return json.dumps({"error": f"Missing required fields: {', '.join(required_fields)}"}), 400

        # Check if cluster with this name already exists
        if mongo_client["labyrinth"]["proxmox_clusters"].find_one({"name": data["name"]}):
            return json.dumps({"error": "Cluster with this name already exists"}), 409

        cluster_doc = {
            "name": data["name"],
            "host": data["host"],
            "user": data["user"],
            "token_id": data["token_id"],
            "token_secret": data["token_secret"],
            "verify_ssl": data.get("verify_ssl", False),
            "created": datetime.datetime.utcnow().isoformat(),
            "updated": datetime.datetime.utcnow().isoformat(),
        }

        result = mongo_client["labyrinth"]["proxmox_clusters"].insert_one(cluster_doc)
        cluster_doc["_id"] = str(result.inserted_id)
        cluster_doc.pop("token_secret", None)

        proxmox_helper.delete_cached_proxmox_disk_data(str(result.inserted_id))

        return json.dumps({"id": str(result.inserted_id), "cluster": cluster_doc}), 201
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/proxmox-clusters/<cluster_id>", methods=["GET"])
@requires_auth_read
def get_proxmox_cluster(cluster_id):
    """
    Get a specific Proxmox cluster configuration
    """
    try:
        cluster = mongo_client["labyrinth"]["proxmox_clusters"].find_one(
            {"_id": bson.ObjectId(cluster_id)}
        )
        if not cluster:
            return json.dumps({"error": "Cluster not found"}), 404

        cluster.pop("token_secret", None)
        return json.dumps(cluster, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/proxmox-clusters/<cluster_id>", methods=["PUT"])
@requires_auth_admin
def update_proxmox_cluster(cluster_id):
    """
    Update a Proxmox cluster configuration
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            return json.dumps({"error": "Invalid JSON body"}), 400

        cluster = mongo_client["labyrinth"]["proxmox_clusters"].find_one(
            {"_id": bson.ObjectId(cluster_id)}
        )
        if not cluster:
            return json.dumps({"error": "Cluster not found"}), 404

        # Update allowed fields
        update_doc = {}
        allowed_fields = ["host", "user", "token_id", "token_secret", "verify_ssl"]
        for field in allowed_fields:
            if field in data:
                update_doc[field] = data[field]

        if update_doc:
            update_doc["updated"] = datetime.datetime.utcnow().isoformat()
            mongo_client["labyrinth"]["proxmox_clusters"].update_one(
                {"_id": bson.ObjectId(cluster_id)},
                {"$set": update_doc}
            )
            proxmox_helper.delete_cached_proxmox_disk_data(cluster_id)

        updated_cluster = mongo_client["labyrinth"]["proxmox_clusters"].find_one(
            {"_id": bson.ObjectId(cluster_id)}
        )
        updated_cluster.pop("token_secret", None)
        return json.dumps(updated_cluster, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/proxmox-clusters/<cluster_id>", methods=["DELETE"])
@requires_auth_admin
def delete_proxmox_cluster(cluster_id):
    """
    Delete a Proxmox cluster configuration
    """
    try:
        proxmox_helper.delete_cached_proxmox_disk_data(cluster_id)
        result = mongo_client["labyrinth"]["proxmox_clusters"].delete_one(
            {"_id": bson.ObjectId(cluster_id)}
        )
        if result.deleted_count == 0:
            return json.dumps({"error": "Cluster not found"}), 404

        return json.dumps({"status": "deleted"}), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/ec2-instances")
@app.route("/aws/ec2-instances/", methods=["GET"])
@requires_auth_read
def get_aws_ec2_instances():
    """
    List EC2 instances across all configured AWS accounts.
    """
    try:
        accounts = list(mongo_client["labyrinth"]["aws_accounts"].find({}))
        result = {
            "accounts": [],
            "instances": [],
            "errors": [],
            "summary": {
                "account_count": len(accounts),
                "instance_count": 0,
                "matched_instance_count": 0,
                "unmatched_instance_count": 0,
            },
        }

        for account in accounts:
            account_name = account.get("name")
            account_region = account.get("region")
            inventory = aws_helper.list_ec2_instances(account)
            result["accounts"].append(
                {
                    "_id": str(account.get("_id")),
                    "name": account_name,
                    "region": account_region,
                }
            )

            if inventory.get("error"):
                result["errors"].append(
                    {
                        "account_name": account_name,
                        "region": account_region,
                        "error": inventory.get("error"),
                    }
                )
                continue

            enriched_instances = _enrich_aws_instances_with_matches(inventory.get("instances", []))
            result["instances"].extend(enriched_instances)

        result["instances"] = sorted(
            result["instances"],
            key=lambda item: (
                _normalize_match_string(item.get("account_name")),
                _normalize_match_string(item.get("region")),
                _normalize_match_string(item.get("name")),
            ),
        )
        result["summary"]["instance_count"] = len(result["instances"])
        result["summary"]["matched_instance_count"] = len(
            [item for item in result["instances"] if item.get("matched")]
        )
        result["summary"]["unmatched_instance_count"] = len(
            [item for item in result["instances"] if not item.get("matched")]
        )

        return json.dumps(result, default=str), 200
    except aws_helper.AWSDependencyError as e:
        return json.dumps({"error": str(e)}), 500
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/accounts")
@app.route("/aws/accounts/", methods=["GET"])
@requires_auth_read
def list_aws_accounts():
    """
    List all configured AWS accounts.
    """
    try:
        accounts = list(mongo_client["labyrinth"]["aws_accounts"].find({}))
        for account in accounts:
            account.pop("secret_access_key", None)
            account.pop("session_token", None)
        return json.dumps(accounts, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/accounts", methods=["POST"])
@app.route("/aws/accounts/", methods=["POST"])
@requires_auth_admin
def create_aws_account():
    """
    Create a new AWS account configuration.
    Expected JSON: {
        "name": "prod-account",
        "region": "us-east-1",
        "access_key_id": "AKIA...",
        "secret_access_key": "...",
        "session_token": "optional"
    }
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            try:
                data = json.loads(request.get_data(as_text=True))
            except (ValueError, json.JSONDecodeError):
                return json.dumps({"error": "Invalid JSON body"}), 400

        required_fields = ["name", "region", "access_key_id", "secret_access_key"]
        if not all(data.get(field) for field in required_fields):
            return json.dumps({"error": f"Missing required fields: {', '.join(required_fields)}"}), 400

        if mongo_client["labyrinth"]["aws_accounts"].find_one({"name": data["name"]}):
            return json.dumps({"error": "AWS account with this name already exists"}), 409

        account_doc = {
            "name": data["name"],
            "region": data["region"],
            "access_key_id": data["access_key_id"],
            "secret_access_key": data["secret_access_key"],
            "session_token": data.get("session_token", ""),
            "created": datetime.datetime.utcnow().isoformat(),
            "updated": datetime.datetime.utcnow().isoformat(),
        }

        result = mongo_client["labyrinth"]["aws_accounts"].insert_one(account_doc)
        created_account = dict(account_doc)
        created_account["_id"] = str(result.inserted_id)
        created_account.pop("secret_access_key", None)
        created_account.pop("session_token", None)

        return json.dumps({"id": str(result.inserted_id), "account": created_account}), 201
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/accounts/<account_id>", methods=["GET"])
@requires_auth_read
def get_aws_account(account_id):
    """
    Get a specific AWS account configuration.
    """
    try:
        account = mongo_client["labyrinth"]["aws_accounts"].find_one(
            {"_id": bson.ObjectId(account_id)}
        )
        if not account:
            return json.dumps({"error": "AWS account not found"}), 404

        account.pop("secret_access_key", None)
        account.pop("session_token", None)
        return json.dumps(account, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/accounts/<account_id>", methods=["PUT"])
@requires_auth_admin
def update_aws_account(account_id):
    """
    Update an AWS account configuration.
    """
    try:
        data = request.get_json(silent=True)
        if data is None:
            return json.dumps({"error": "Invalid JSON body"}), 400

        account = mongo_client["labyrinth"]["aws_accounts"].find_one(
            {"_id": bson.ObjectId(account_id)}
        )
        if not account:
            return json.dumps({"error": "AWS account not found"}), 404

        update_doc = {}
        allowed_fields = ["name", "region", "access_key_id", "secret_access_key", "session_token"]
        for field in allowed_fields:
            if field not in data:
                continue
            if field in ["secret_access_key", "session_token"] and not data.get(field):
                continue
            update_doc[field] = data[field]

        if update_doc.get("name") and update_doc["name"] != account.get("name"):
            duplicate = mongo_client["labyrinth"]["aws_accounts"].find_one(
                {"name": update_doc["name"]}
            )
            if duplicate:
                return json.dumps({"error": "AWS account with this name already exists"}), 409

        if update_doc:
            update_doc["updated"] = datetime.datetime.utcnow().isoformat()
            mongo_client["labyrinth"]["aws_accounts"].update_one(
                {"_id": bson.ObjectId(account_id)},
                {"$set": update_doc}
            )

        updated_account = mongo_client["labyrinth"]["aws_accounts"].find_one(
            {"_id": bson.ObjectId(account_id)}
        )
        updated_account.pop("secret_access_key", None)
        updated_account.pop("session_token", None)
        return json.dumps(updated_account, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/accounts/<account_id>", methods=["DELETE"])
@requires_auth_admin
def delete_aws_account(account_id):
    """
    Delete an AWS account configuration.
    """
    try:
        result = mongo_client["labyrinth"]["aws_accounts"].delete_one(
            {"_id": bson.ObjectId(account_id)}
        )
        if result.deleted_count == 0:
            return json.dumps({"error": "AWS account not found"}), 404

        return json.dumps({"status": "deleted"}), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


@app.route("/aws/settings")
@app.route("/aws/settings/", methods=["GET"])
@requires_auth_read
def get_aws_settings():
    """
    Get AWS inventory settings.
    """
    try:
        accounts = list(mongo_client["labyrinth"]["aws_accounts"].find({}))
        sanitized_accounts = []
        for account in accounts:
            account.pop("secret_access_key", None)
            account.pop("session_token", None)
            account["_id"] = str(account["_id"])
            sanitized_accounts.append(account)

        return json.dumps({"accounts": sanitized_accounts}, default=str), 200
    except Exception as e:
        return json.dumps({"error": str(e)}), 500


if __name__ == "__main__":  # pragma: no cover
    # Check on indexes
    index_helper()

    if len(sys.argv) > 1 and sys.argv[1] == "watcher":
        unwrap(dashboard)(report=True)
    elif len(sys.argv) > 1 and sys.argv[1] == "updater":
        with PidFile("labyrinth-bulk-insert") as p:
            unwrap(bulk_insert)()
    else:
        app.debug = True
        app.config["ENV"] = "development"
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 7000)))
