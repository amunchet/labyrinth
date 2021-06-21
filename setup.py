#!/usr/bin/env python
"""
Setup script for Vue+Auth0 Quickstart Template
"""
from pprint import pprint
import os
import subprocess
import shutil
import json
import sys
from distutils.util import strtobool

def inplace_change(filename, old_string, new_string):
    """
    Credit to https://stackoverflow.com/questions/4128144/replace-string-within-file-contents
    """
    # Safely read the input filename using 'with'
    with open(filename) as f:
        s = f.read()
        if old_string not in s:
            print('"{old_string}" not found in {filename}.'.format(**locals()))
            return

    # Safely write the changed content, if found in the file
    with open(filename, 'w') as f:
        print('Changing "{old_string}" to "{new_string}" in {filename}'.format(**locals()))
        s = s.replace(old_string, new_string)
        f.write(s)

def user_yes_no_query(question):
    """From https://stackoverflow.com/questions/3041986/apt-command-line-interface-like-yes-no-input"""

    sys.stdout.write('%s [y/n]\n' % question)
    while True:
        try:
            return strtobool(input().lower())
        except ValueError:
            sys.stdout.write('Please respond with \'y\' or \'n\'.\n')


if __name__ == "__main__":

    if "frontend" not in os.listdir(".") and "setup.py" not in os.listdir("."):
        raise Exception("Script called from the wrong directory.  Please change directories to the directory with setup.py in it.")

    try:
        subprocess.call("docker")
    except:
        raise Exception("Docker is not installed.  Please install before continuing.")


    clear = lambda: subprocess.call('cls||clear', shell=True)
    clear()
    print("----------------------------------------------")
    print("Welcome to the Vue+Auth0 Setup script")

    print("We assume you have python and docker installed.")
    print("----------------------------------------------")

    print()
    print()


    # ----------------------------------------------------------
    # Project Name
    # ----------------------------------------------------------
    print("Please enter your project's name: ")
    project_name = input().strip()

    if not project_name.isalnum():
        raise Exception("ERROR - Project name can only contain numbers or letters")


    file_list = [
        "frontend/entrypoint.sh",
        "frontend/project_name/package-lock.json",
        "frontend/project_name/package.json",
        "frontend/project_name/README.md",
        "docker-compose.yml.snippet"
    ]

    for f in file_list:
        inplace_change(f, "XXPROJECTNAMEXX", project_name)


    clear()

    # ----------------------------------------------------------
    # Auth Config Section
    # ----------------------------------------------------------

    auth_config = {}
    auth_config_file = "frontend/project_name/src/auth_config.json"
    if os.path.exists(auth_config_file):
        print("Auth0 config JSON already found!")
    else:
        print("Please enter Auth0 domain: ")
        auth_config["domain"] = input().strip()

        print("Please enter Auth0 clientId: ")
        auth_config["clientId"] = input().strip()

        print("Please enter Auth0 audience: ")
        auth_config["audience"] = input().strip()

        with open(auth_config_file, "w") as f:
            json.dump(auth_config, f)

    clear()
    # ----------------------------------------------------------
    # Setting URL Prefix
    # ----------------------------------------------------------
    print("Please enter URL prefix (i.e. dist) - no leading slash needed")
    url_prefix = input().strip()

    inplace_change("frontend/project_name/vue.config.js", "XXURLPATHXX", "/" + url_prefix)

    clear()

    # ----------------------------------------------------------
    # Docker section
    #   - Port for Vue
    #   - Port for Vue UI
    # ----------------------------------------------------------
    print("Please enter port for Vue: ")
    vue_port = input().strip()
    print("Please enter port for Vue UI: ")
    vue_port_ui = input().strip()

    inplace_change("docker-compose.yml.snippet", "XXVUEPORTXX", vue_port)
    inplace_change("docker-compose.yml.snippet", "XXVUEUIPORTXX", vue_port_ui)

    rename = user_yes_no_query("Do you wish to rename the docker snippet to docker-compose.yml?")

    if rename:
        os.rename("docker-compose.yml.snippet", "docker-compose.yml")

    # ----------------------------------------------------------
    # Remove .git?
    # ----------------------------------------------------------
    clear()
    remove = user_yes_no_query("Do you wish to remove the .git directory? ")

    if remove:
        remove_confirm = user_yes_no_query("Are you sure? ")


    if remove and remove_confirm:
        shutil.rmtree(".git")

    # ----------------------------------------------------------
    # Final Directory Rename
    # ----------------------------------------------------------
    # Last step is to rename the directory to the project project_name
    print("Final rename...")
    os.rename("frontend/project_name/", "frontend/" + project_name)

    # ----------------------------------------------------------
    # Start Docker
    # ----------------------------------------------------------
    
    start_docker = user_yes_no_query("Start docker? ")
    
    if start_docker:
        os.system("docker-compose up --build -d")
        print("Please note that Vue will need some additional time to start up.  Attach to the docker logs to see the progress.")


    print ("Project creation created!  Enjoy.")