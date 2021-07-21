#!/usr/bin/env python3

# TODO: I can delete most of this file

"""
Tests for modifying Telegraf TOML
    - Going to save created sections in a `snippets` folder.
    - Once finished, will compile all the folder snippets into the final
"""


def test_list_all_sections(): 
    """Lists all the sections wtih [[ and ]] in them """

    retval = [
        "[[inputs.cpu]]", 
        "[[inputs.iptables]]"
    ]

def test_read_section():
    """
    Returns everything from the beginning of [[NAME]] to the next instance of [[]] or the EOF

    E.g.
    ----
    # # Configuration for Amon Server to send metrics to.
    # [[outputs.amon]]
    #   ## Amon Server Key
    #   server_key = "my-server-key" # required.
    #
    #   ## Amon Instance URL
    #   amon_instance = "https://youramoninstance" # required
    #
    #   ## Connection timeout.
    #   # timeout = "5s"


    # # Publishes metrics to an AMQP broker

    TODO: annoying with the next item coming in.  Might check if second to last row is blank
        - If so, skip last row as it's the next sections comment
    """

def test_create_edit_snippet():
    """
    Creates a TOML snippet
        - Must verify that the TOML is acceptable


    !!EACH SNIPPET IS GOING TO BE A SERVICE NAME!!
    """

def test_delete_snippet():
    """
    Tests deleting a snippet
        - This will have deleting service implications as well
    """

def test_compile_snippets():
    """
    Tests compiling the snippets, then running a telegraf instance with them
        - Must verify that the TOML is good
    

    EACH COMPILATION WILL BE HOST SPECIFIC - IT WILL BE DETERMINED BY THE SERVICES SELECTED

    """