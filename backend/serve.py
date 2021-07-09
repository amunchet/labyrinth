#!/usr/bin/env python3
"""
Sample Flask app
"""
# Permissions scope names
import functools
import os

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
