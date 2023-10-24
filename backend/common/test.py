#!/usr/bin/env python3
"""
Common functions for testing.
"""


def unwrap(f):
    """
    Unwraps the function down to the last layer of __wrapped__.  This is used in testing functions that have been wrapped with a decorator (such as the security ones).
    """
    found = False
    b = f
    count = 0
    while not found:
        try:
            b = b.__wrapped__
            count += 1
        except AttributeError:
            found = True
    if count == 0:
        raise Exception("Unwrapped Exception Found.")
    return b

def delete_keys_recursive(data, search="_id"):
    if isinstance(data, dict):
        for key in list(data.keys()):
            if key == search:
                del data[key]
            else:
                delete_keys_recursive(data[key])
    elif isinstance(data, list):
        for item in data:
            delete_keys_recursive(item)