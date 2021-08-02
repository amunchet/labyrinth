#!/usr/bin/env python3

from glob import glob

DIR="/src/labyrinth/*/*/*.vue"
TEMPLATE="/src/labyrinth/tests/unit/example.template"
PARTIAL="/src/labyrinth/src"

def last_part(item):
    return item.split("/")[-1]

def path(item):
    return "/".join(item.split("/")[:-1])

with open(TEMPLATE) as f:
    template = f.read()

for item in glob(DIR):
    with open(path(TEMPLATE) + "/" + last_part(item).replace(".vue", ".spec.js"), "w") as f:
        f.write(
            template
                .replace("{{FNAME}}", last_part(item))
                .replace("{{PATH}}", item.replace(PARTIAL, "@")))

