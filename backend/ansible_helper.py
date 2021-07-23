#!/usr/bin/env python3
"""
Ansible helper functions
"""
import os
import subprocess
import shutil
import uuid

def check_file(filename, file_type, raw=""):
    """
    Verifies the file uploaded is a valid file of the specified type
    """
    retval = False
    temp_file = "/tmp/{}".format(str(uuid.uuid1()))
    
    look_file = "/src/uploads/{}/{}".format(file_type,filename)
    if raw == ""  and not os.path.exists(look_file):
        return False

    if file_type == "ansible" and filename and raw != "":
        # We have a raw data to write out
        with open(temp_file, "w") as f:
            f.write(raw)
        
        x = subprocess.run(["ansible-playbook {} --check".format(temp_file)], shell=True, capture_output=True)
        if x.returncode >= 4:
            retval = False
        else:
            retval = True
        
        if retval:
            if not os.path.exists("/src/uploads/ansible"):
                os.mkdir("/src/uploads/ansible")
            shutil.move(temp_file, "/src/uploads/ansible/{}.yml".format(filename))
        
        return retval

    elif file_type == "ansible":
        x = subprocess.run(["ansible-playbook {} --check".format(look_file)], shell=True, capture_output=True)
        if x.returncode >= 4:
            retval = False
        else:
            retval = True
        return retval

    elif file_type == "telegraf":

        if os.path.exists("/etc/telegraf/telegraf.conf"):
            os.remove("/etc/telegraf/telegraf.conf")
        
        shutil.copy(look_file, "/etc/telegraf/telegraf.conf")

        x = subprocess.run(["telegraf --test"], shell=True, capture_output=True)
        if x.returncode != 0:
            retval = False
        else:
            retval = True

        os.remove("/etc/telegraf/telegraf.conf")
        return retval

    elif file_type == "other":
        return True
    else:
        # Checking for encrypted file
        with open(look_file) as f:
            count = 0
            for item in f.readlines():
                if count == 0 :
                    if "ANSIBLE_VAULT" in item:
                        return True
                break
        return False

def run_ansible():
    """
    Runs ansible playbook
    """