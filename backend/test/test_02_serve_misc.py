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


def test_auth_failure_on_routes_with_url_arguments():
    """
    A missing token is a 401 on every protected route, including routes with
    URL arguments (the auth decorator passes those on to error_func)
    """
    client = serve.app.test_client()
    assert client.get("/secure").status_code == 401
    assert client.get("/host/AA").status_code == 401
    assert client.get("/custom_dashboard_images/floorplan.jpg").status_code == 401

    # The UI shows this text, so auth.py's message must not come back escaped
    body = client.get("/secure").get_data(as_text=True)
    assert body.startswith("Auth Error 401 - {'code': ")
