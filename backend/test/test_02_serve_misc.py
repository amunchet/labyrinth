"""
Various additional functions from `serve.py`
"""
"""
- Insecure and secure routes check

- List all files in an upload type (list_uploads)
- List specific host (list_host(host=""))

- Loads in a TOML file (load_service(name, format="json"))

- Test save_conf (host, data = "", raw = "")
- Test run Telegraf conf file (run_telegraf)

"""
import os
import json

import serve

from common.test import unwrap
def test_insecure():
    assert serve.insecure()[1] == 200

def test_secure():
    """Tests secure route"""
    assert unwrap(serve.secure)()[1] == 200

def test_list_uploads():
    """
    Tests Listing the uploads of a given folder type
    """
    a = unwrap(serve.list_uploads)("bdadgas")
    assert a[1] == 409

    a = unwrap(serve.list_uploads)("become")
    assert a[1] == 200

    b = os.listdir("/src/uploads/become")
    assert json.loads(a[0]) == b