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
def test_insecure():
    assert False