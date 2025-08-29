import json
from ai import main as app_main

def test_ignores_non_monitored_hosts_and_warning_host_level():
    data = [
        {
            "groups": [
                {
                    "hosts": [
                        {"host": "ignored-1", "monitor": False, "services": [
                            {"name": "svc", "state": False}
                        ]},
                        {"host": "ignored-2", "monitor": True, "service_level": "warning", "services": [
                            {"name": "svc", "state": False}
                        ]},
                        {"host": "kept", "monitor": True, "services": [
                            {"name": "svc", "state": False}
                        ]},
                    ]
                }
            ]
        }
    ]
    out = json.loads(app_main.process_dashboard(data))
    assert out == [["kept", ["svc", {"state": False}]]]

def test_ignores_services_set_to_warning_level_for_host():
    data = [
        {
            "groups": [
                {
                    "hosts": [
                        {
                            "host": "app-1",
                            "monitor": True,
                            "service_levels": [
                                {"service": "svc_ok_as_warning", "level": "warning"}
                            ],
                            "services": [
                                {"name": "svc_ok_as_warning", "state": False},
                                {"name": "svc_real_fail", "state": False},
                            ],
                        }
                    ]
                }
            ]
        }
    ]
    out = json.loads(app_main.process_dashboard(data))
    assert out == [["app-1", ["svc_real_fail", {"state": False}]]]

def test_ignores_new_host_and_open_closed_ports_failures():
    data = [
        {
            "groups": [
                {
                    "hosts": [
                        {
                            "ip": "10.0.0.9",
                            "monitor": True,
                            "services": [
                                {"name": "new_host", "state": False},
                                {"name": "open_ports", "state": False},
                                {"name": "closed_ports", "state": False},
                                {"name": "real", "state": False},
                            ],
                        }
                    ]
                }
            ]
        }
    ]
    out = json.loads(app_main.process_dashboard(data))
    assert out == [["10.0.0.9", ["real", {"state": False}]]]
