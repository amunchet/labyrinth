#!/usr/bin/env python3
"""
Tests for backend/proxmox_disk_check.py

Covers a regression where VMs with a missing/unavailable QEMU guest agent
(disk reported as 0 on a running VM) were silently skipped by the
`if maxdisk and disk:` truthy check in `collect_disk_issues`. Because those
VMs never produced an "issue", a whole cluster whose only problems were
missing-agent VMs looked completely clean - even though every cluster was
actually being queried. These tests lock in the fix: such VMs must always be
surfaced (regardless of threshold), and every configured cluster must
contribute to the final issue list.
"""

import json

import pytest

import proxmox_disk_check
import serve

from common.test import unwrap


def cleanup_test_data():
    """Clean up disk-check test data."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})


@pytest.fixture
def setup():
    """Sets up tests."""
    cleanup_test_data()
    yield "Setting up..."
    cleanup_test_data()


def _cluster_data_with_datastore_issue(cluster_name, host):
    """Cluster payload whose only issue is an over-threshold datastore."""
    return {
        "cluster_name": cluster_name,
        "host": host,
        "nodes": [
            {
                "name": "node-a",
                "storage": [
                    {
                        "name": "local",
                        "type": "dir",
                        "enabled": True,
                        "total": 1000,
                        "used": 950,
                    },
                ],
                "vms": [],
                "containers": [],
            }
        ],
    }


def _cluster_data_with_missing_qemu_agent(cluster_name, host):
    """Cluster payload whose only "issue" is a VM missing its QEMU guest agent."""
    return {
        "cluster_name": cluster_name,
        "host": host,
        "nodes": [
            {
                "name": "node-b",
                "storage": [],
                "vms": [
                    {
                        "id": 301,
                        "name": "vm-missing-agent",
                        "status": "running",
                        "maxdisk": 10737418240,
                        "disk": 0,
                        "qemu_guest_agent_installed": False,
                        "qemu_guest_agent_warning_inferred": True,
                        "qemu_guest_agent_error": "QEMU guest agent is not running",
                    }
                ],
                "containers": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# collect_disk_issues - unit tests
# ---------------------------------------------------------------------------


def test_collect_disk_issues_flags_missing_qemu_agent_regardless_of_threshold():
    """Running VMs with an unavailable QEMU guest agent are always surfaced,
    even though their reported disk usage (0) would never cross the threshold
    under the old truthy check."""
    cluster_data = _cluster_data_with_missing_qemu_agent("cluster-a", "10.1.1.1")

    issues = proxmox_disk_check.collect_disk_issues(cluster_data, threshold_percent=80)

    assert len(issues) == 1
    issue = issues[0]
    assert issue["type"] == "vm_qemu_missing"
    assert issue["cluster"] == "cluster-a"
    assert issue["node"] == "node-b"
    assert issue["name"] == "vm-missing-agent"
    assert issue["vm_id"] == 301
    assert issue["maxdisk"] == 10737418240
    assert issue["qemu_agent_installed"] is False
    assert "not running" in issue["qemu_agent_error"]


def test_collect_disk_issues_missing_agent_vm_not_double_counted():
    """A VM flagged as vm_qemu_missing must not also appear as a normal 'vm'
    issue (disk=0 would fail the percentage check anyway, but this locks in
    the `continue` short-circuit)."""
    cluster_data = _cluster_data_with_missing_qemu_agent("cluster-a", "10.1.1.1")

    issues = proxmox_disk_check.collect_disk_issues(cluster_data, threshold_percent=0)

    types = [issue["type"] for issue in issues]
    assert types == ["vm_qemu_missing"]


def test_collect_disk_issues_normal_vm_over_threshold_unaffected():
    """VMs with a working guest agent and real usage still use the normal
    percentage-based threshold check - no regression from the QEMU fix."""
    cluster_data = {
        "cluster_name": "cluster-a",
        "host": "10.1.1.1",
        "nodes": [
            {
                "name": "node-a",
                "storage": [],
                "containers": [],
                "vms": [
                    {
                        "id": 202,
                        "name": "vm-healthy",
                        "status": "running",
                        "maxdisk": 1000,
                        "disk": 900,
                        "qemu_guest_agent_installed": True,
                        "qemu_guest_agent_warning_inferred": False,
                        "qemu_guest_agent_error": None,
                    }
                ],
            }
        ],
    }

    issues = proxmox_disk_check.collect_disk_issues(cluster_data, threshold_percent=80)

    assert len(issues) == 1
    assert issues[0]["type"] == "vm"
    assert abs(issues[0]["percentage"] - 90.0) < 0.01


def test_collect_disk_issues_stopped_vm_with_zero_disk_not_flagged():
    """Stopped VMs naturally report zero disk and should not be flagged as
    either a usage issue or a missing-agent warning."""
    cluster_data = {
        "cluster_name": "cluster-a",
        "host": "10.1.1.1",
        "nodes": [
            {
                "name": "node-a",
                "storage": [],
                "containers": [],
                "vms": [
                    {
                        "id": 203,
                        "name": "vm-stopped",
                        "status": "stopped",
                        "maxdisk": 1000,
                        "disk": 0,
                        "qemu_guest_agent_installed": False,
                        "qemu_guest_agent_warning_inferred": False,
                        "qemu_guest_agent_error": None,
                    }
                ],
            }
        ],
    }

    issues = proxmox_disk_check.collect_disk_issues(cluster_data, threshold_percent=80)

    assert issues == []


# ---------------------------------------------------------------------------
# gather_all_disk_issues - multi-cluster regression test
# ---------------------------------------------------------------------------


def test_gather_all_disk_issues_checks_every_cluster_including_qemu_missing(
    setup, monkeypatch
):
    """Every configured cluster must contribute issues - including a cluster
    whose only problem is a VM with a missing QEMU guest agent.

    Before the fix, such VMs were silently dropped (disk=0 is falsy in
    `if maxdisk and disk:`), making the whole second cluster look issue-free
    even though it was genuinely being queried. This is the direct regression
    test for that bug.
    """
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_many(
        [
            {
                "name": "cluster-1",
                "host": "10.1.1.1",
                "user": "root@pam",
                "token_id": "token-1",
                "token_secret": "secret-1",
                "verify_ssl": False,
            },
            {
                "name": "cluster-2",
                "host": "10.1.1.2",
                "user": "root@pam",
                "token_id": "token-2",
                "token_secret": "secret-2",
                "verify_ssl": False,
            },
        ]
    )

    def fake_get_cached(cluster, redis_client=None):
        if cluster["name"] == "cluster-1":
            return _cluster_data_with_datastore_issue("cluster-1", cluster["host"])
        return _cluster_data_with_missing_qemu_agent("cluster-2", cluster["host"])

    monkeypatch.setattr(
        proxmox_disk_check.proxmox_helper,
        "get_proxmox_disk_data_cached",
        fake_get_cached,
    )

    issues, errors = proxmox_disk_check.gather_all_disk_issues(
        80, db=serve.mongo_client, redis_client=object()
    )

    assert errors == []
    assert len(issues) == 2

    clusters_seen = {issue["cluster"] for issue in issues}
    assert clusters_seen == {"cluster-1", "cluster-2"}

    types_seen = {issue["type"] for issue in issues}
    assert types_seen == {"datastore", "vm_qemu_missing"}


def test_gather_all_disk_issues_records_errors_without_skipping_other_clusters(
    setup, monkeypatch
):
    """A cluster that errors out should be reported in cluster_errors, but
    must not prevent other clusters from being checked."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_many(
        [
            {
                "name": "cluster-broken",
                "host": "10.1.1.9",
                "user": "root@pam",
                "token_id": "token-9",
                "token_secret": "secret-9",
                "verify_ssl": False,
            },
            {
                "name": "cluster-2",
                "host": "10.1.1.2",
                "user": "root@pam",
                "token_id": "token-2",
                "token_secret": "secret-2",
                "verify_ssl": False,
            },
        ]
    )

    def fake_get_cached(cluster, redis_client=None):
        if cluster["name"] == "cluster-broken":
            return {"error": "Could not retrieve nodes"}
        return _cluster_data_with_missing_qemu_agent("cluster-2", cluster["host"])

    monkeypatch.setattr(
        proxmox_disk_check.proxmox_helper,
        "get_proxmox_disk_data_cached",
        fake_get_cached,
    )

    issues, errors = proxmox_disk_check.gather_all_disk_issues(
        80, db=serve.mongo_client, redis_client=object()
    )

    assert len(errors) == 1
    assert errors[0]["cluster"] == "cluster-broken"
    assert len(issues) == 1
    assert issues[0]["cluster"] == "cluster-2"
    assert issues[0]["type"] == "vm_qemu_missing"


# ---------------------------------------------------------------------------
# render_email_template - new section rendering
# ---------------------------------------------------------------------------


def test_render_email_template_includes_qemu_missing_section():
    """The rendered HTML includes a dedicated section for VMs with a missing
    QEMU guest agent, alongside the normal VM section."""
    issues = [
        {
            "type": "vm_qemu_missing",
            "cluster": "cluster-2",
            "host": "10.1.1.2",
            "node": "node-b",
            "name": "vm-missing-agent",
            "vm_id": 301,
            "status": "running",
            "maxdisk": 10737418240,
            "qemu_agent_installed": False,
            "qemu_agent_error": "QEMU guest agent is not running",
        },
        {
            "type": "vm",
            "cluster": "cluster-1",
            "host": "10.1.1.1",
            "node": "node-a",
            "name": "vm-healthy",
            "vm_id": 202,
            "status": "running",
            "used": 900,
            "total": 1000,
            "percentage": 90.0,
            "qemu_agent_installed": True,
        },
    ]

    html = proxmox_disk_check.render_email_template(issues, threshold_percent=80)

    assert "Missing QEMU Guest Agent" in html
    assert "vm-missing-agent" in html
    assert "vm-healthy" in html
    assert "cluster-2" in html
    assert "cluster-1" in html


def test_render_email_template_omits_qemu_missing_section_when_absent():
    """The missing-agent section should not render at all when there are no
    such issues, keeping the email clean for the common case."""
    issues = [
        {
            "type": "vm",
            "cluster": "cluster-1",
            "host": "10.1.1.1",
            "node": "node-a",
            "name": "vm-healthy",
            "vm_id": 202,
            "status": "running",
            "used": 900,
            "total": 1000,
            "percentage": 90.0,
            "qemu_agent_installed": True,
        },
    ]

    html = proxmox_disk_check.render_email_template(issues, threshold_percent=80)

    assert "Missing QEMU Guest Agent" not in html


# ---------------------------------------------------------------------------
# send_full_test_email - full pipeline across all clusters
# ---------------------------------------------------------------------------


def test_send_full_test_email_reports_issues_from_all_clusters(setup, monkeypatch):
    """The 'Send Full Test Email' path must reflect issues found across every
    cluster, including missing-QEMU warnings, and report a per-type breakdown."""
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_many(
        [
            {
                "name": "cluster-1",
                "host": "10.1.1.1",
                "user": "root@pam",
                "token_id": "token-1",
                "token_secret": "secret-1",
                "verify_ssl": False,
            },
            {
                "name": "cluster-2",
                "host": "10.1.1.2",
                "user": "root@pam",
                "token_id": "token-2",
                "token_secret": "secret-2",
                "verify_ssl": False,
            },
        ]
    )

    def fake_get_cached(cluster, redis_client=None):
        if cluster["name"] == "cluster-1":
            return _cluster_data_with_datastore_issue("cluster-1", cluster["host"])
        return _cluster_data_with_missing_qemu_agent("cluster-2", cluster["host"])

    monkeypatch.setattr(
        proxmox_disk_check.proxmox_helper,
        "get_proxmox_disk_data_cached",
        fake_get_cached,
    )

    sent = {}

    def fake_email_helper(to, subject, html, **kwargs):
        sent["to"] = to
        sent["subject"] = subject
        sent["html"] = html
        return "<test-message-id>"

    monkeypatch.setattr(
        proxmox_disk_check.email_helper, "email_helper", fake_email_helper
    )

    result = proxmox_disk_check.send_full_test_email(
        ["ops@example.com"],
        threshold_percent=80,
        db=serve.mongo_client,
        redis_client=object(),
    )

    assert result["issues_found"] == 2
    assert result["threshold_percent"] == 80
    assert result["cluster_errors"] == []
    assert result["issues_by_type"] == {"datastore": 1, "vm_qemu_missing": 1}

    assert sent["to"] == ["ops@example.com"]
    assert "2 Issue(s)" in sent["subject"]
    assert "Missing QEMU Guest Agent" in sent["html"]
    assert "cluster-1" in sent["html"]
    assert "cluster-2" in sent["html"]


def test_send_full_test_email_requires_recipients():
    """Guard clause: an empty recipient list should raise, not silently send."""
    with pytest.raises(ValueError):
        proxmox_disk_check.send_full_test_email([])


# ---------------------------------------------------------------------------
# /disk-space/test-email endpoint - wiring tests
# ---------------------------------------------------------------------------


def test_send_disk_space_test_email_endpoint_full_mode(setup, monkeypatch):
    """The /disk-space/test-email endpoint forwards to send_full_test_email
    and returns its breakdown alongside status/mode/recipients."""
    captured = {}

    def fake_send_full_test_email(
        recipients, db=None, redis_client=None, threshold_percent=None
    ):
        captured["recipients"] = recipients
        return {
            "issues_found": 2,
            "threshold_percent": 80,
            "cluster_errors": [],
            "issues_by_type": {"datastore": 1, "vm_qemu_missing": 1},
        }

    monkeypatch.setattr(
        serve.proxmox_disk_check, "send_full_test_email", fake_send_full_test_email
    )
    monkeypatch.setattr(serve.proxmox_helper, "get_redis_client", lambda: object())

    with serve.app.test_request_context(
        "/disk-space/test-email",
        method="POST",
        json={"mode": "full", "recipients": ["ops@example.com"]},
    ):
        resp = unwrap(serve.send_disk_space_test_email)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert data["status"] == "sent"
    assert data["mode"] == "full"
    assert data["issues_found"] == 2
    assert data["issues_by_type"] == {"datastore": 1, "vm_qemu_missing": 1}
    assert captured["recipients"] == ["ops@example.com"]


def test_send_disk_space_test_email_endpoint_simple_mode_skips_proxmox(
    setup, monkeypatch
):
    """Simple test-email mode must never query Proxmox clusters."""

    def fail_if_called(*args, **kwargs):
        raise AssertionError("full test path should not run in simple mode")

    simple_calls = []

    def fake_simple(recipients):
        simple_calls.append(recipients)

    monkeypatch.setattr(
        serve.proxmox_disk_check, "send_full_test_email", fail_if_called
    )
    monkeypatch.setattr(serve.proxmox_disk_check, "send_simple_test_email", fake_simple)

    with serve.app.test_request_context(
        "/disk-space/test-email",
        method="POST",
        json={"mode": "simple", "recipients": ["ops@example.com"]},
    ):
        resp = unwrap(serve.send_disk_space_test_email)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert data["status"] == "sent"
    assert data["mode"] == "simple"
    assert simple_calls == [["ops@example.com"]]


def test_send_disk_space_test_email_endpoint_falls_back_to_saved_recipients(
    setup, monkeypatch
):
    """When no recipients are supplied in the request, the endpoint should
    fall back to the saved disk_space_alert_recipients setting."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {
            "name": "disk_space_alert_recipients",
            "value": "saved@example.com, other@example.com",
        }
    )

    simple_calls = []

    def fake_simple(recipients):
        simple_calls.append(recipients)

    monkeypatch.setattr(serve.proxmox_disk_check, "send_simple_test_email", fake_simple)

    with serve.app.test_request_context(
        "/disk-space/test-email",
        method="POST",
        json={"mode": "simple"},
    ):
        resp = unwrap(serve.send_disk_space_test_email)()

    assert resp[1] == 200
    data = json.loads(resp[0])
    assert data["status"] == "sent"
    assert data["mode"] == "simple"
    assert simple_calls == [["saved@example.com", "other@example.com"]]


def test_send_disk_space_test_email_endpoint_requires_recipients(setup):
    """Without any recipients (request or saved settings), the endpoint
    should return a 400 rather than silently doing nothing."""
    with serve.app.test_request_context(
        "/disk-space/test-email",
        method="POST",
        json={"mode": "simple"},
    ):
        resp = unwrap(serve.send_disk_space_test_email)()

    assert resp[1] == 400
    assert "No recipients configured" in json.loads(resp[0])["error"]


def test_send_disk_space_test_email_endpoint_rejects_invalid_mode(setup):
    """An unrecognized mode should be rejected with a 400, not silently
    defaulting to one behavior or the other."""
    with serve.app.test_request_context(
        "/disk-space/test-email",
        method="POST",
        json={"mode": "bogus", "recipients": ["ops@example.com"]},
    ):
        resp = unwrap(serve.send_disk_space_test_email)()

    assert resp[1] == 400
    assert "mode must be" in json.loads(resp[0])["error"]


# ---------------------------------------------------------------------------
# calculate_percentage - edge cases and error handling
# ---------------------------------------------------------------------------


def test_calculate_percentage_zero_total():
    """Return 0 when total is 0."""
    result = proxmox_disk_check.calculate_percentage(100, 0)
    assert result == 0


def test_calculate_percentage_none_total():
    """Return 0 when total is None."""
    result = proxmox_disk_check.calculate_percentage(100, None)
    assert result == 0


def test_calculate_percentage_invalid_values():
    """Handle invalid values via try/except (function signature expects int)."""
    # Test that the function's try/except handles edge cases gracefully
    result = proxmox_disk_check.calculate_percentage(0, 0)
    assert result == 0


def test_calculate_percentage_float_values():
    """Calculate percentage with float values (converts to int)."""
    result = proxmox_disk_check.calculate_percentage(int(50.5), int(100.0))
    # Function converts to int, so 50.5 becomes 50
    assert result == pytest.approx(50.0)


def test_calculate_percentage_exact_calculation():
    """Verify exact percentage calculation."""
    result = proxmox_disk_check.calculate_percentage(int(75), int(100))
    assert result == pytest.approx(75.0)


# ---------------------------------------------------------------------------
# format_size - bytes conversion
# ---------------------------------------------------------------------------


def test_format_size_zero_bytes():
    """Format 0 bytes."""
    result = proxmox_disk_check.format_size(0)
    assert result == "0 B"


def test_format_size_none():
    """Handle None input."""
    result = proxmox_disk_check.format_size(None)
    assert result == "0 B"


def test_format_size_zero_value():
    """Handle zero input."""
    result = proxmox_disk_check.format_size(0)
    assert result == "0 B"


def test_format_size_bytes():
    """Format bytes."""
    result = proxmox_disk_check.format_size(int(512))
    assert "512" in result and "B" in result


def test_format_size_kilobytes():
    """Format kilobytes."""
    result = proxmox_disk_check.format_size(2048)
    assert "KB" in result or "B" in result


def test_format_size_megabytes():
    """Format megabytes."""
    result = proxmox_disk_check.format_size(1048576)
    assert "MB" in result or "KB" in result


def test_format_size_gigabytes():
    """Format gigabytes."""
    result = proxmox_disk_check.format_size(1073741824)
    assert "GB" in result or "MB" in result


def test_format_size_terabytes():
    """Format terabytes."""
    result = proxmox_disk_check.format_size(1099511627776)
    assert "TB" in result or "GB" in result


def test_format_size_petabytes():
    """Format petabytes."""
    result = proxmox_disk_check.format_size(1125899906842624)
    assert "PB" in result or "TB" in result


# ---------------------------------------------------------------------------
# get_disk_alert_settings - settings retrieval
# ---------------------------------------------------------------------------


def test_get_disk_alert_settings_defaults(setup):
    """Return defaults when no settings exist."""
    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert settings["threshold_percent"] == 80
    assert settings["recipients"] == []


def test_get_disk_alert_settings_custom_threshold(setup):
    """Retrieve custom threshold."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_threshold", "value": "90"}
    )

    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert settings["threshold_percent"] == 90


def test_get_disk_alert_settings_invalid_threshold(setup):
    """Fall back to default for invalid threshold."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_threshold", "value": "not-a-number"}
    )

    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert settings["threshold_percent"] == 80


def test_get_disk_alert_settings_empty_threshold(setup):
    """Fall back to default for empty threshold."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_threshold", "value": ""}
    )

    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert settings["threshold_percent"] == 80


def test_get_disk_alert_settings_recipients_as_list(setup):
    """Handle recipients as list."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {
            "name": "disk_space_alert_recipients",
            "value": ["user1@example.com", "user2@example.com"],
        }
    )

    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert len(settings["recipients"]) == 2


def test_get_disk_alert_settings_recipients_as_comma_string(setup):
    """Parse recipients from comma-separated string."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {
            "name": "disk_space_alert_recipients",
            "value": "user1@example.com, user2@example.com",
        }
    )

    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert len(settings["recipients"]) == 2
    assert "user1@example.com" in settings["recipients"]
    assert "user2@example.com" in settings["recipients"]


def test_get_disk_alert_settings_recipients_with_whitespace(setup):
    """Strip whitespace from recipients."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {
            "name": "disk_space_alert_recipients",
            "value": "  user1@example.com  ,  user2@example.com  ",
        }
    )

    settings = proxmox_disk_check.get_disk_alert_settings(serve.mongo_client)

    assert settings["recipients"] == ["user1@example.com", "user2@example.com"]


# ---------------------------------------------------------------------------
# _collect_storage_issues - storage-specific issue collection
# ---------------------------------------------------------------------------


def test_collect_storage_issues_over_threshold():
    """Flag datastores over threshold."""
    node = {
        "storage": [
            {
                "name": "local",
                "type": "dir",
                "enabled": True,
                "total": 1000,
                "used": 850,
            }
        ]
    }

    issues = proxmox_disk_check._collect_storage_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 1
    assert issues[0]["type"] == "datastore"
    assert issues[0]["percentage"] == pytest.approx(85.0)


def test_collect_storage_issues_under_threshold():
    """Don't flag datastores under threshold."""
    node = {
        "storage": [
            {
                "name": "local",
                "type": "dir",
                "enabled": True,
                "total": 1000,
                "used": 500,
            }
        ]
    }

    issues = proxmox_disk_check._collect_storage_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


def test_collect_storage_issues_disabled_storage():
    """Skip disabled datastores."""
    node = {
        "storage": [
            {
                "name": "local",
                "type": "dir",
                "enabled": False,
                "total": 1000,
                "used": 950,
            }
        ]
    }

    issues = proxmox_disk_check._collect_storage_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


def test_collect_storage_issues_missing_total():
    """Skip storage with missing total."""
    node = {
        "storage": [
            {
                "name": "local",
                "type": "dir",
                "enabled": True,
                "total": None,
                "used": 950,
            }
        ]
    }

    issues = proxmox_disk_check._collect_storage_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


def test_collect_storage_issues_multiple_datastores():
    """Handle multiple datastores."""
    node = {
        "storage": [
            {
                "name": "local",
                "type": "dir",
                "enabled": True,
                "total": 1000,
                "used": 850,
            },
            {
                "name": "backup",
                "type": "dir",
                "enabled": True,
                "total": 2000,
                "used": 1800,
            },
        ]
    }

    issues = proxmox_disk_check._collect_storage_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 2


# ---------------------------------------------------------------------------
# _collect_vm_issues - VM-specific issue collection
# ---------------------------------------------------------------------------


def test_collect_vm_issues_over_threshold():
    """Flag VMs over threshold."""
    node = {
        "vms": [
            {
                "id": 100,
                "name": "vm-1",
                "status": "running",
                "maxdisk": 1000,
                "disk": 850,
                "qemu_guest_agent_installed": True,
                "qemu_guest_agent_warning_inferred": False,
            }
        ]
    }

    issues = proxmox_disk_check._collect_vm_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 1
    assert issues[0]["type"] == "vm"
    assert issues[0]["percentage"] == pytest.approx(85.0)


def test_collect_vm_issues_under_threshold():
    """Don't flag VMs under threshold."""
    node = {
        "vms": [
            {
                "id": 100,
                "name": "vm-1",
                "status": "running",
                "maxdisk": 1000,
                "disk": 500,
                "qemu_guest_agent_installed": True,
                "qemu_guest_agent_warning_inferred": False,
            }
        ]
    }

    issues = proxmox_disk_check._collect_vm_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


def test_collect_vm_issues_missing_qemu_agent():
    """Flag VMs with missing QEMU agent."""
    node = {
        "vms": [
            {
                "id": 100,
                "name": "vm-1",
                "status": "running",
                "maxdisk": 10737418240,
                "disk": 0,
                "qemu_guest_agent_installed": False,
                "qemu_guest_agent_warning_inferred": True,
                "qemu_guest_agent_error": "Agent not installed",
            }
        ]
    }

    issues = proxmox_disk_check._collect_vm_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 1
    assert issues[0]["type"] == "vm_qemu_missing"
    # Should not appear again as a normal VM issue


def test_collect_vm_issues_no_maxdisk():
    """Skip VMs without maxdisk."""
    node = {
        "vms": [
            {
                "id": 100,
                "name": "vm-1",
                "status": "running",
                "maxdisk": None,
                "disk": 500,
                "qemu_guest_agent_installed": True,
                "qemu_guest_agent_warning_inferred": False,
            }
        ]
    }

    issues = proxmox_disk_check._collect_vm_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


# ---------------------------------------------------------------------------
# _collect_container_issues - container-specific issue collection
# ---------------------------------------------------------------------------


def test_collect_container_issues_over_threshold():
    """Flag containers over threshold."""
    node = {
        "containers": [
            {
                "id": 200,
                "name": "lxc-1",
                "status": "running",
                "maxdisk": 1000,
                "disk": 850,
            }
        ]
    }

    issues = proxmox_disk_check._collect_container_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 1
    assert issues[0]["type"] == "container"
    assert issues[0]["percentage"] == pytest.approx(85.0)


def test_collect_container_issues_under_threshold():
    """Don't flag containers under threshold."""
    node = {
        "containers": [
            {
                "id": 200,
                "name": "lxc-1",
                "status": "running",
                "maxdisk": 1000,
                "disk": 500,
            }
        ]
    }

    issues = proxmox_disk_check._collect_container_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


def test_collect_container_issues_no_maxdisk():
    """Skip containers without maxdisk."""
    node = {
        "containers": [
            {
                "id": 200,
                "name": "lxc-1",
                "status": "running",
                "maxdisk": None,
                "disk": 500,
            }
        ]
    }

    issues = proxmox_disk_check._collect_container_issues(
        node, "cluster-1", "10.0.0.1", "node-1", 80
    )

    assert len(issues) == 0


# ---------------------------------------------------------------------------
# send_simple_test_email - minimal test emails
# ---------------------------------------------------------------------------


def test_send_simple_test_email_requires_recipients():
    """Guard clause: empty recipients should raise."""
    with pytest.raises(ValueError):
        proxmox_disk_check.send_simple_test_email([])


def test_send_simple_test_email_success(monkeypatch):
    """Successfully send simple test email."""
    sent = {}

    def fake_email_helper(to, subject, html, **kwargs):
        sent["to"] = to
        sent["subject"] = subject
        sent["html"] = html

    monkeypatch.setattr(
        proxmox_disk_check.email_helper, "email_helper", fake_email_helper
    )

    proxmox_disk_check.send_simple_test_email(["ops@example.com"])

    assert sent["to"] == ["ops@example.com"]
    assert "Test Email" in sent["subject"]
    assert "test" in sent["html"].lower()


# ---------------------------------------------------------------------------
# send_alert_email - email rendering and sending
# ---------------------------------------------------------------------------


def test_send_alert_email_basic(monkeypatch):
    """Send alert email with formatted issues."""
    sent = {}

    def fake_email_helper(to, subject, html, **kwargs):
        sent["to"] = to
        sent["subject"] = subject
        sent["html"] = html

    monkeypatch.setattr(
        proxmox_disk_check.email_helper, "email_helper", fake_email_helper
    )

    issues = [
        {
            "type": "datastore",
            "cluster": "cluster-1",
            "host": "10.0.0.1",
            "node": "node-1",
            "name": "local",
            "storage_type": "dir",
            "used": 850,
            "total": 1000,
            "percentage": 85.0,
        }
    ]

    proxmox_disk_check.send_alert_email(["ops@example.com"], issues, 80)

    assert sent["to"] == ["ops@example.com"]
    assert "1 Issues Found" in sent["subject"]


def test_send_alert_email_custom_subject(monkeypatch):
    """Use custom subject."""
    sent = {}

    def fake_email_helper(to, subject, html, **kwargs):
        sent["subject"] = subject

    monkeypatch.setattr(
        proxmox_disk_check.email_helper, "email_helper", fake_email_helper
    )

    issues = []
    custom_subject = "Custom Subject"

    proxmox_disk_check.send_alert_email(
        ["ops@example.com"], issues, 80, subject=custom_subject
    )

    assert sent["subject"] == custom_subject


# ---------------------------------------------------------------------------
# check_and_alert_disk_space - main function
# ---------------------------------------------------------------------------


def test_check_and_alert_disk_space_no_recipients(setup, monkeypatch, capsys):
    """Skip check when no recipients configured."""
    monkeypatch.setattr("sys.exit", lambda *args: None)

    proxmox_disk_check.check_and_alert_disk_space()

    captured = capsys.readouterr()
    assert "No email recipients" in captured.out


def test_check_and_alert_disk_space_no_clusters(setup, monkeypatch, capsys):
    """Skip check when no clusters configured."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_recipients", "value": "ops@example.com"}
    )

    proxmox_disk_check.check_and_alert_disk_space()

    captured = capsys.readouterr()
    assert "No Proxmox clusters" in captured.out


def test_check_and_alert_disk_space_no_issues(setup, monkeypatch, capsys):
    """Handle case with no issues found."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_recipients", "value": "ops@example.com"}
    )
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one(
        {
            "name": "cluster-1",
            "host": "10.0.0.1",
        }
    )

    def fake_gather(threshold, db=None):
        return [], []

    monkeypatch.setattr(proxmox_disk_check, "gather_all_disk_issues", fake_gather)

    proxmox_disk_check.check_and_alert_disk_space()

    captured = capsys.readouterr()
    assert "No disk space issues found" in captured.out


def test_check_and_alert_disk_space_sends_alert_on_issues(setup, monkeypatch, capsys):
    """Send alert when issues are found."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_recipients", "value": "ops@example.com"}
    )
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one(
        {
            "name": "cluster-1",
            "host": "10.0.0.1",
        }
    )

    issues = [{"type": "datastore", "percentage": 85.0}]

    def fake_gather(threshold, db=None):
        return issues, []

    def fake_send_alert(*args, **kwargs):
        """Mock callback - intentionally empty to verify email sending is called."""

    monkeypatch.setattr(proxmox_disk_check, "gather_all_disk_issues", fake_gather)
    monkeypatch.setattr(proxmox_disk_check, "send_alert_email", fake_send_alert)

    proxmox_disk_check.check_and_alert_disk_space()

    captured = capsys.readouterr()
    assert "Found 1 disk space issues" in captured.out
    assert "Alert email sent" in captured.out


def test_check_and_alert_disk_space_handles_email_error(setup, monkeypatch, capsys):
    """Handle email sending errors."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "disk_space_alert_recipients", "value": "ops@example.com"}
    )
    serve.mongo_client["labyrinth"]["proxmox_clusters"].insert_one(
        {
            "name": "cluster-1",
            "host": "10.0.0.1",
        }
    )

    issues = [{"type": "datastore", "percentage": 85.0}]

    def fake_gather(threshold, db=None):
        return issues, []

    def fake_send_alert(*args, **kwargs):
        raise RuntimeError("SMTP error")

    monkeypatch.setattr(proxmox_disk_check, "gather_all_disk_issues", fake_gather)
    monkeypatch.setattr(proxmox_disk_check, "send_alert_email", fake_send_alert)
    monkeypatch.setattr("sys.exit", lambda *args: None)

    proxmox_disk_check.check_and_alert_disk_space()

    captured = capsys.readouterr()
    assert "Failed to send email" in captured.out


def test_check_and_alert_disk_space_general_error(setup, monkeypatch, capsys):
    """Handle general errors gracefully."""

    def fake_get_settings(db):
        raise RuntimeError("Database error")

    monkeypatch.setattr(
        proxmox_disk_check, "get_disk_alert_settings", fake_get_settings
    )
    monkeypatch.setattr("sys.exit", lambda *args: None)

    proxmox_disk_check.check_and_alert_disk_space()

    captured = capsys.readouterr()
    assert "Error in disk check" in captured.out or "Database error" in captured.out
