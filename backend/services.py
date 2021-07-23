#!/usr/bin/env python3
"""
Services functions
    - TOML parser - how to handle the master Telegraf conf file?
"""

import os
import shutil

import toml
import re
from typing import List


def prepare(fname="/src/uploads/master.conf") -> List:
    """
    Step 1
        - reads in the individual lines of the TOML file
        - remove comments as best we cannot

    :returns - Array of lines
    """
    lines = []
    decoder = toml.TomlPreserveCommentDecoder(beforeComments=True)

    if not os.path.exists(fname):
        # Copy over the defaults
        shutil.copy("/src/uploads/defaults/telegraf.conf", fname) 

    with open(fname) as f:

        in_array = False
        array_count = 0

        seen_keys = []
        seen_sections = []

        for (line_no, line) in enumerate(f.readlines()):
            parsed_line = re.sub(r'^(\s?#?)+', '', line).strip()

            # Duplicate sections

            if parsed_line and parsed_line[0] == "[" and not in_array:
                if parsed_line in seen_sections:
                    lines.append(line)
                    continue

                seen_keys = []
                seen_sections.append(parsed_line)

            try:
                # Duplicate keys

                found_key = parsed_line.split("=")[0].strip()
                found_arr = [x for x in seen_keys if x[0] == found_key]
                if found_arr:
                    # Comment out the found items in lines
                    for x in found_arr:
                        if x[0] != "":

                            if lines[x[1]][-1] != "[":
                                # Normal case
                                lines[x[1]] = "# {}".format(lines[x[1]])
                            else:
                                # What if we have a multi-line array?
                                count = x[1]
                                while lines[count][-1] != "]":
                                    lines[count] = "# {}".format(lines[count])
                                    count += 1
                                lines[count] = "# {}".format(lines[count])

                if "=" in parsed_line:
                    seen_keys.append((found_key, line_no))

                # Handle multiline arrays
                if in_array and parsed_line:
                    if "[" not in parsed_line:
                        lines[-1+array_count] = "{} {}".format(
                            lines[-1+array_count], parsed_line)
                    array_count -= 1
                    lines.append("")
                    
                    if parsed_line[-1] == "]":
                        in_array = False
                        array_count = 0
                else:
                    # Is this line valid toml?
                    toml.loads(parsed_line, decoder=decoder)
                    lines.append(parsed_line)

                    if parsed_line and parsed_line[-1] == "[":
                        in_array = True

            except Exception as e:
                lines.append(line)

    return lines


def parse(item) -> dict:
    """
    Recursive parse of a CommentValue filled toml data structure.
        - Removes comments

    :returns - Dictionary of object
    """
    if type(item) == toml.decoder.CommentValue:

        retval = parse(item.val)

        return retval
    elif type(item) == type([]):

        retval = []
        for x in item:
            retval.append(parse(x))

        return retval
    elif type(item) == type({}):

        retval = {}
        for x in item:
            retval[x] = parse(item[x])

        return retval
    else:

        return item


def find_comments(lines):
    """
    Searches through the uncommented (`prepare` was run on it) file and records comments

        - ends in ], then that's a header - clear the parent
        - if there's no #... and a `=` in it, then everything before it is a key
        - If the line starts with a `#`, then it's a comment
    """

    retval = []
    current_parent = ""
    current_comments = []
    current_key = ""

    for line in [x.strip() for x in lines if x.strip() != ""]:
        # Is this a comment?
        if re.match("^(\s?#+)+", line):
            current_comments.append(line)
        else:
            # Section or array of sections
            if line[-1] == "]" and "=" not in line:
                current_parent = line.strip()
                if "]]" in line and "[[" in line:
                    retval.append({"name": current_parent, "comments": current_comments, "multiple" : True})
                else:
                    retval.append({"name": current_parent, "comments": current_comments})
                current_comments = []
            # Key
            elif "=" in line:
                current_key = current_parent + "." + line.split("=")[0]
                current_value = line.split("=")[1].strip()
                # Inline comments
                if "#" in line:
                    current_comments.append(line.split("#")[1])
                retval.append({"name": current_key.strip(), "comments": current_comments, "parent": current_parent, "value" : current_value})
                current_comments = []
    return retval
