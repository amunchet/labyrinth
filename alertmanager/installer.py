#!/usr/bin/env python3
"""
Check to ensure alertmanager has a password set
"""
import bcrypt
import yaml
import string
import secrets
import os


def generate_random_password():
    """
    Generates a random password
    """
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(0,64))

def load_yml(filename="/src/webconfig.yml"):
    """
    Loads YAML file
    """
    if not os.path.exists(filename):
        return {}
    return yaml.safe_load(open(filename))

def add_password_if_not_present(yml, password):
    """
    Checks if password is present in structure
    If not, encrypts it with bcrypt and adds it to the structure
    """
    hashed = bcrypt.hashpw(password.encode('ascii'), bcrypt.gensalt())


    retval = yml
    if not yml:
        retval = {}


    retval["basic_auth_users"] = {
        "admin" : hashed.decode("utf-8")
    }
    return retval


def write_yml(yml, filename="/src/webconfig.yml"):
    """
    Writes out yml structure to disk
    """
    with open(filename, "w") as f:
        f.write(yaml.dump(yml))


def write_pass(password, filename="/src/pass"):
    """
    Writes out the randomly generated password for labyrinth UI to show to admins
    """
    with open(filename, "w") as f:
        f.write(password)

if __name__ == '__main__':
    print("Starting alertmanager password installer...")

    password = generate_random_password()
    yml = load_yml()
    yml = add_password_if_not_present(yml, password)
    write_yml(yml)
    write_pass(password)
    print("Done")