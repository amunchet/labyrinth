#!/usr/bin/env python3
"""
Tests for backend/ai/ai_pipeline.py - the dashboard-processing / ChatGPT /
render-email logic shared by the hourly AI alert cron job and the on-demand
"Send Test Email" button, and imported directly by serve.py (via the
/ai/test-email route), so it needs its own direct coverage here rather than
only through backend/ai/test/ (which isn't part of this gated suite).
"""

import json
import os

import pytest

from ai import ai_pipeline


def test_process_dashboard_matches_sample_output():
    """Full pass over the sample fixture used by ai/test/test_main.py."""
    with open(os.path.join("ai", "sample_input.json")) as f:
        sample_input = json.load(f)
    with open(os.path.join("ai", "sample_output.json")) as f:
        sample_output = json.load(f)

    assert json.loads(ai_pipeline.process_dashboard(sample_input)) == sample_output


def test_process_dashboard_ignores_non_monitored_hosts_and_warning_host_level():
    data = [
        {
            "groups": [
                {
                    "hosts": [
                        {
                            "host": "ignored-1",
                            "monitor": False,
                            "services": [{"name": "svc", "state": False}],
                        },
                        {
                            "host": "ignored-2",
                            "monitor": True,
                            "service_level": "warning",
                            "services": [{"name": "svc", "state": False}],
                        },
                        {
                            "host": "kept",
                            "monitor": True,
                            "services": [{"name": "svc", "state": False}],
                        },
                    ]
                }
            ]
        }
    ]
    out = json.loads(ai_pipeline.process_dashboard(data))
    assert out == [
        {"host": "kept", "failing": ["svc", {"state": False}], "all_services": ["svc"]}
    ]


def test_process_dashboard_ignores_services_downgraded_to_warning():
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
    out = json.loads(ai_pipeline.process_dashboard(data))
    assert out == [
        {
            "host": "app-1",
            "failing": ["svc_real_fail", {"state": False}],
            "all_services": ["svc_ok_as_warning", "svc_real_fail"],
        }
    ]


def test_process_dashboard_ignores_internal_service_names():
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
    out = json.loads(ai_pipeline.process_dashboard(data))
    assert out == [
        {
            "host": "10.0.0.9",
            "failing": ["real", {"state": False}],
            "all_services": ["real"],
        }
    ]


def test_process_dashboard_resolves_service_names_and_slims_metrics():
    data = [
        {
            "groups": [
                {
                    "hosts": [
                        {
                            "host": "host-with-only-passing-services",
                            "monitor": True,
                            "services": [{"name": "healthy", "state": True}],
                        },
                        {
                            "host": "host-with-named-fallbacks",
                            "monitor": True,
                            "services": [
                                {
                                    # no "name" and no "found_service" at all: name
                                    # resolution gives up and the service is skipped
                                    "state": False,
                                },
                                {
                                    "state": False,
                                    "found_service": "string_fallback_name",
                                },
                                {
                                    "state": False,
                                    "found_service": {
                                        "display_name": "dict_fallback_name",
                                        "metric": "response_time",
                                    },
                                },
                                {
                                    "name": "with_full_metric",
                                    "state": False,
                                    "latest_metric": {
                                        "name": "http_response",
                                        "timestamp": 1700000000.0,
                                        "fields": {"result_code": 3},
                                        "tags": {"server": "10.0.0.1"},
                                    },
                                },
                                {
                                    "name": "with_empty_tags",
                                    "state": False,
                                    "latest_metric": {
                                        "fields": {"state": True},
                                        "tags": {"unrecognized_tag": "x"},
                                    },
                                },
                                {
                                    "name": "with_bare_metric",
                                    "state": False,
                                    "latest_metric": {"name": "bare"},
                                },
                            ],
                        },
                    ]
                }
            ]
        }
    ]

    out = json.loads(ai_pipeline.process_dashboard(data))

    # host with only a passing service produces no result entry at all
    assert all(entry["host"] != "host-with-only-passing-services" for entry in out)

    fallback_entry = next(
        entry for entry in out if entry["host"] == "host-with-named-fallbacks"
    )
    assert fallback_entry["all_services"] == [
        "string_fallback_name",
        "dict_fallback_name",
        "with_full_metric",
        "with_empty_tags",
        "with_bare_metric",
    ]

    # "failing" is a flat [name, slim, name, slim, ...] list; pair them up by name
    failing_pairs = dict(
        zip(fallback_entry["failing"][0::2], fallback_entry["failing"][1::2])
    )

    assert failing_pairs["string_fallback_name"] == {
        "state": False,
        "found_service": {"name": "string_fallback_name"},
    }
    assert failing_pairs["dict_fallback_name"] == {
        "state": False,
        "found_service": {
            "display_name": "dict_fallback_name",
            "metric": "response_time",
        },
    }
    assert failing_pairs["with_full_metric"] == {
        "state": False,
        "latest_metric": {
            "name": "http_response",
            "timestamp": 1700000000.0,
            "fields": {"result_code": 3},
            "tags": {"server": "10.0.0.1"},
        },
    }
    # "state" is a recognized field key but unrecognized tag keys are dropped,
    # and an empty/unrecognized tags dict is dropped entirely (unlike fields)
    assert failing_pairs["with_empty_tags"] == {
        "state": False,
        "latest_metric": {"fields": {"state": True}},
    }
    # a metric with no "fields"/"tags" keys at all slims down to just the name
    assert failing_pairs["with_bare_metric"] == {
        "state": False,
        "latest_metric": {"name": "bare"},
    }


def test_render_email_html_empty_alerts():
    assert ai_pipeline.render_email_html([]) == "<p>No active alerts.</p>"
    assert ai_pipeline.render_email_html(None) == "<p>No active alerts.</p>"


def test_render_email_html_renders_rows_with_connection_badge():
    alerts = [
        {
            "host": "api-1",
            "severity": "critical",
            "likely_connection_issue": True,
            "failing_services": ["db_conn", "http"],
            "notes": "Multiple services down.",
        },
        {
            "host": "api-2",
            "severity": "warning",
            "likely_connection_issue": False,
            "failing_services": [],
            "notes": "",
        },
    ]

    html = ai_pipeline.render_email_html(alerts)

    assert "api-1" in html
    assert "CRITICAL" in html
    assert "possible connection issue" in html
    assert "db_conn, http" in html
    assert "api-2" in html
    assert "WARNING" in html
    assert "—" in html  # empty failing_services renders as an em dash


def test_send_simple_test_email_requires_recipients():
    with pytest.raises(ValueError):
        ai_pipeline.send_simple_test_email(
            [], {"subject_template": "X", "from_name": "Bot"}
        )
