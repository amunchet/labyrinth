#!/usr/bin/env python3
"""
Services functions
    - TOML parser - how to handle the master Telegraf conf file?
"""

import toml
import re
from typing import List

decoder = toml.TomlPreserveCommentDecoder(beforeComments = True)

def prepare(fname="/src/uploads/master.conf") -> List:
    """
    Step 1 
        - reads in the individual lines of the TOML file 
        - remove comments as best we cannot

    :returns - Array of lines
    """
    lines = []
    with open(fname) as f:
        
        in_array = False
        seen_keys = []
        seen_sections = []


        for (line_no, line) in enumerate(f.readlines()):
            parsed_line = re.sub(r'^(\s?#?)+', '',line).strip()

            if parsed_line and parsed_line[-1] == "[":
                in_array = True
            

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
                if in_array and parsed_line and parsed_line[-1] != "]":
                    lines.append(parsed_line)
                elif in_array and parsed_line and parsed_line[-1] == "]":
                    lines.append(parsed_line)
                    in_array = False
                else:
                    toml.loads(parsed_line, decoder=decoder)
                    lines.append(parsed_line)
            except Exception as e:
                lines.append(line)

    return lines
