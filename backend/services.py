#!/usr/bin/env python3
"""
Services functions
    - TOML parser - how to handle the master Telegraf conf file?
"""

import toml
import re

decoder = toml.TomlPreserveCommentDecoder(beforeComments = True)

def step_1(fname="/src/uploads/master.conf"):
    """
    Step 1 - reads in the individual lines of the TOML file and remove comments as best we cannot

    NOTE: This will NOT work properly with multiline arrays.  That's why step 2 is required.
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
                # We assume duplicate keys are next to each other


                found_key = parsed_line.split("=")[0].strip()
                found_arr = [x for x in seen_keys if x[0] == found_key]
                if found_arr:
                    # Comment out the last item in lines
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
                    output = toml.loads(parsed_line, decoder=decoder)
                    lines.append(parsed_line)
            except Exception as e:
                lines.append(line)

    with open("output-labyrinth", "w") as f:
        for line in lines:
            f.write(line)
    return lines
"""
def step_2():
    "
    Step 2 - splits the given file into many different sections.  
    From there, we need to re-run our regular expressions and determine if EACH SECTION is valid TOML (no longer each file)

    Then we will recombine into one file and allow comments to be parsed
    "
    with open("output-labyrinth") as f:
        retval = ""
        
        saved_information = ""
        for line in f.readlines():
            if line[0] == "[":
                if saved_information != "":
                    
                    parsed = ""
                    for idx, item in enumerate(saved_information.split("\n")):
                        parsed_line = re.sub(r'^(\s?#?)+', '', item) + "\n"
                        try:
                            if idx > 0:
                                toml.loads("\n".join(saved_information[:idx-1]))
                        except Exception as e:

                    


                    saved_information = ""
            else:
                saved_information += line
        
"""