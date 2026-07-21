#!/usr/bin/env python3
"""
Tests for backend/ec2_unmatched_check.py and its serve.py wiring
(/aws/settings recipients, /aws/test-email).
"""

import json

import pytest

import ec2_unmatched_check
import serve

from common.test import unwrap


def cleanup_test_data():
    """Clean up EC2 unmatched-check test data."""
    serve.mongo_client["labyrinth"]["aws_accounts"].delete_many({})
    serve.mongo_client["labyrinth"]["hosts"].delete_many({})
    serve.mongo_client["labyrinth"]["settings"].delete_many({})


@pytest.fixture
def setup():
    """Sets up tests."""
    cleanup_test_data()
    yield "Setting up..."
    cleanup_test_data()


def _account(name="prod-account", region="us-east-1"):
    return {
        "name": name,
        "region": region,
        "access_key_id": "AKIAXXXXX",
        "secret_access_key": "secret-value",
    }


def _instance(instance_id, private_ip, name=None):
    return {
        "instance_id": instance_id,
        "name": name or instance_id,
        "state": "running",
        "instance_type": "t3.medium",
        "private_ip": private_ip,
        "public_ip": None,
        "private_dns_name": f"{instance_id}.ec2.internal",
        "public_dns_name": "",
        "availability_zone": "us-east-1a",
        "subnet_id": "subnet-123",
        "vpc_id": "vpc-123",
        "platform": "linux",
        "architecture": "x86_64",
        "monitoring_state": "enabled",
        "launch_time": "2026-07-08T00:00:00",
        "tags": {"Name": name or instance_id},
        "security_groups": [],
        "account_id": "123456789012",
        "region": "us-east-1",
        "account_name": "prod-account",
    }


# ---------------------------------------------------------------------------
# get_ec2_alert_settings
# ---------------------------------------------------------------------------


def test_get_ec2_alert_settings_defaults(setup):
    """No saved recipients defaults to an empty list."""
    settings = ec2_unmatched_check.get_ec2_alert_settings(serve.mongo_client)
    assert settings["recipients"] == []


def test_get_ec2_alert_settings_recipients_as_list(setup):
    """Recipients saved as a list pass through unchanged."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": ["a@example.com", "b@example.com"]}
    )
    settings = ec2_unmatched_check.get_ec2_alert_settings(serve.mongo_client)
    assert settings["recipients"] == ["a@example.com", "b@example.com"]


def test_get_ec2_alert_settings_recipients_as_comma_string(setup):
    """Recipients saved as a comma-separated string are split and trimmed."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "a@example.com, b@example.com"}
    )
    settings = ec2_unmatched_check.get_ec2_alert_settings(serve.mongo_client)
    assert settings["recipients"] == ["a@example.com", "b@example.com"]


# ---------------------------------------------------------------------------
# gather_unmatched_instances
# ---------------------------------------------------------------------------


def test_gather_unmatched_instances_filters_matched_hosts(setup, monkeypatch):
    """Only instances without a matching Labyrinth host are returned."""
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(_account())
    serve.mongo_client["labyrinth"]["hosts"].insert_one(
        {
            "ip": "10.0.0.10",
            "mac": "00-11-22-33-44-55",
            "host": "ip-10-0-0-10",
            "group": "AWS",
            "services": [],
            "monitor": "true",
            "tags": "aws",
        }
    )

    def fake_list_ec2_instances(account_config):
        return {
            "account_name": account_config["name"],
            "region": account_config["region"],
            "instances": [
                _instance("i-matched", "10.0.0.10"),
                _instance("i-unmatched", "10.0.0.99"),
            ],
        }

    monkeypatch.setattr(
        ec2_unmatched_check.aws_helper, "list_ec2_instances", fake_list_ec2_instances
    )

    unmatched, errors = ec2_unmatched_check.gather_unmatched_instances(
        db=serve.mongo_client
    )

    assert errors == []
    assert len(unmatched) == 1
    assert unmatched[0]["instance_id"] == "i-unmatched"
    assert unmatched[0]["matched"] is False


def test_gather_unmatched_instances_records_errors_without_skipping_other_accounts(
    setup, monkeypatch
):
    """One broken AWS account shouldn't block collection from the others."""
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_many(
        [_account("broken-account"), _account("good-account")]
    )

    def fake_list_ec2_instances(account_config):
        if account_config["name"] == "broken-account":
            return {
                "account_name": "broken-account",
                "region": "us-east-1",
                "error": "AuthFailure",
                "instances": [],
            }
        return {
            "account_name": "good-account",
            "region": "us-east-1",
            "instances": [_instance("i-unmatched", "10.0.0.99")],
        }

    monkeypatch.setattr(
        ec2_unmatched_check.aws_helper, "list_ec2_instances", fake_list_ec2_instances
    )

    unmatched, errors = ec2_unmatched_check.gather_unmatched_instances(
        db=serve.mongo_client
    )

    assert len(errors) == 1
    assert errors[0]["account_name"] == "broken-account"
    assert errors[0]["error"] == "AuthFailure"
    assert len(unmatched) == 1
    assert unmatched[0]["instance_id"] == "i-unmatched"


# ---------------------------------------------------------------------------
# render_email_template
# ---------------------------------------------------------------------------


def test_render_email_template_lists_unmatched_instances():
    """Rendered HTML includes unmatched instance details."""
    html = ec2_unmatched_check.render_email_template(
        [_instance("i-unmatched", "10.0.0.99", name="db-server-1")]
    )
    assert "db-server-1" in html
    assert "i-unmatched" in html
    assert "10.0.0.99" in html


def test_render_email_template_empty_list():
    """Rendered HTML shows the all-clear message when nothing is unmatched."""
    html = ec2_unmatched_check.render_email_template([])
    assert "All EC2 instances are currently matched" in html


# ---------------------------------------------------------------------------
# send_alert_email / send_simple_test_email / send_full_test_email
# ---------------------------------------------------------------------------


def test_send_alert_email_default_subject(monkeypatch):
    """Default subject includes the unmatched instance count."""
    captured = {}

    def fake_email_helper(to, subject, html, **kwargs):
        captured["to"] = to
        captured["subject"] = subject
        captured["html"] = html

    monkeypatch.setattr(
        ec2_unmatched_check.email_helper, "email_helper", fake_email_helper
    )

    ec2_unmatched_check.send_alert_email(
        ["a@example.com"], [_instance("i-unmatched", "10.0.0.99")]
    )

    assert captured["to"] == ["a@example.com"]
    assert "1 Instance(s) Found" in captured["subject"]


def test_send_alert_email_custom_subject(monkeypatch):
    """A custom subject overrides the default."""
    captured = {}

    def fake_email_helper(to, subject, html, **kwargs):
        captured["subject"] = subject

    monkeypatch.setattr(
        ec2_unmatched_check.email_helper, "email_helper", fake_email_helper
    )

    ec2_unmatched_check.send_alert_email(["a@example.com"], [], subject="Custom")
    assert captured["subject"] == "Custom"


def test_send_simple_test_email_requires_recipients():
    """Raises ValueError with no recipients."""
    with pytest.raises(ValueError):
        ec2_unmatched_check.send_simple_test_email([])


def test_send_simple_test_email_success(monkeypatch):
    """Sends a static test email without querying AWS."""
    captured = {}

    def fake_email_helper(to, subject, html, **kwargs):
        captured["to"] = to
        captured["subject"] = subject

    monkeypatch.setattr(
        ec2_unmatched_check.email_helper, "email_helper", fake_email_helper
    )

    ec2_unmatched_check.send_simple_test_email(["a@example.com"])
    assert captured["to"] == ["a@example.com"]
    assert "Test Email" in captured["subject"]


def test_send_full_test_email_requires_recipients():
    """Raises ValueError with no recipients."""
    with pytest.raises(ValueError):
        ec2_unmatched_check.send_full_test_email([])


def test_send_full_test_email_sends_even_with_no_unmatched_instances(
    setup, monkeypatch
):
    """Full test email always sends, even when nothing is unmatched."""
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(_account())

    def fake_list_ec2_instances(account_config):
        return {
            "account_name": account_config["name"],
            "region": account_config["region"],
            "instances": [],
        }

    monkeypatch.setattr(
        ec2_unmatched_check.aws_helper, "list_ec2_instances", fake_list_ec2_instances
    )

    sent = {}

    def fake_email_helper(to, subject, html, **kwargs):
        sent["subject"] = subject

    monkeypatch.setattr(
        ec2_unmatched_check.email_helper, "email_helper", fake_email_helper
    )

    result = ec2_unmatched_check.send_full_test_email(
        ["a@example.com"], db=serve.mongo_client
    )

    assert result["unmatched_found"] == 0
    assert result["account_errors"] == []
    assert "[TEST]" in sent["subject"]


# ---------------------------------------------------------------------------
# check_and_alert_unmatched_instances - main entrypoint
# ---------------------------------------------------------------------------


def test_check_and_alert_no_recipients(setup, monkeypatch, capsys):
    """Skips (no exception) when no recipients are configured."""
    ec2_unmatched_check.check_and_alert_unmatched_instances()
    captured = capsys.readouterr()
    assert "No email recipients configured" in captured.out


def test_check_and_alert_no_accounts(setup, monkeypatch, capsys):
    """Skips when recipients exist but no AWS accounts are configured."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "a@example.com"}
    )
    ec2_unmatched_check.check_and_alert_unmatched_instances()
    captured = capsys.readouterr()
    assert "No AWS accounts configured" in captured.out


def test_check_and_alert_no_unmatched_instances(setup, monkeypatch, capsys):
    """Prints a clean-bill message and doesn't send email when nothing is unmatched."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "a@example.com"}
    )
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(_account())

    monkeypatch.setattr(
        ec2_unmatched_check, "gather_unmatched_instances", lambda db=None: ([], [])
    )

    ec2_unmatched_check.check_and_alert_unmatched_instances()
    captured = capsys.readouterr()
    assert "No unmatched EC2 instances found" in captured.out


def test_check_and_alert_sends_alert_on_unmatched_instances(setup, monkeypatch, capsys):
    """Sends an alert email when unmatched instances are found."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "a@example.com"}
    )
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(_account())

    monkeypatch.setattr(
        ec2_unmatched_check,
        "gather_unmatched_instances",
        lambda db=None: ([_instance("i-unmatched", "10.0.0.99")], []),
    )

    sent = {}

    def fake_send_alert(recipients, instances, subject=None):
        sent["recipients"] = recipients
        sent["instances"] = instances

    monkeypatch.setattr(ec2_unmatched_check, "send_alert_email", fake_send_alert)

    ec2_unmatched_check.check_and_alert_unmatched_instances()
    captured = capsys.readouterr()
    assert "Found 1 unmatched EC2 instance(s)" in captured.out
    assert sent["recipients"] == ["a@example.com"]


def test_check_and_alert_handles_email_error(setup, monkeypatch, capsys):
    """Exits with an error status if the alert email fails to send."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "a@example.com"}
    )
    serve.mongo_client["labyrinth"]["aws_accounts"].insert_one(_account())

    monkeypatch.setattr(
        ec2_unmatched_check,
        "gather_unmatched_instances",
        lambda db=None: ([_instance("i-unmatched", "10.0.0.99")], []),
    )

    def fake_send_alert(recipients, instances, subject=None):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr(ec2_unmatched_check, "send_alert_email", fake_send_alert)
    monkeypatch.setattr("sys.exit", lambda *args: None)

    ec2_unmatched_check.check_and_alert_unmatched_instances()
    captured = capsys.readouterr()
    assert "Failed to send email" in captured.out


def test_check_and_alert_general_error(setup, monkeypatch, capsys):
    """A general exception is caught, logged, and exits with an error status."""
    monkeypatch.setattr(
        ec2_unmatched_check,
        "get_mongo_client",
        lambda: (_ for _ in ()).throw(RuntimeError("connection failed")),
    )
    monkeypatch.setattr("sys.exit", lambda *args: None)

    ec2_unmatched_check.check_and_alert_unmatched_instances()
    captured = capsys.readouterr()
    assert "Error in EC2 unmatched check" in captured.out


# ---------------------------------------------------------------------------
# serve.py wiring: GET /aws/settings recipients, POST /aws/test-email
# ---------------------------------------------------------------------------


def test_get_aws_settings_includes_ec2_alert_recipients(setup):
    """The AWS settings endpoint returns saved EC2 alert recipients."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "a@example.com, b@example.com"}
    )

    response = unwrap(serve.get_aws_settings)()
    assert response[1] == 200
    payload = json.loads(response[0])
    assert payload["ec2_alert_recipients"] == ["a@example.com", "b@example.com"]


def test_send_ec2_test_email_endpoint_simple_mode(setup, monkeypatch):
    """POST /aws/test-email simple mode sends without querying AWS."""

    def fake_simple(recipients):
        assert recipients == ["a@example.com"]

    monkeypatch.setattr(serve.ec2_unmatched_check, "send_simple_test_email", fake_simple)

    with serve.app.test_request_context(
        "/aws/test-email",
        method="POST",
        json={"mode": "simple", "recipients": ["a@example.com"]},
    ):
        resp = unwrap(serve.send_ec2_unmatched_test_email)()

    assert resp[1] == 200
    payload = json.loads(resp[0])
    assert payload["status"] == "sent"
    assert payload["mode"] == "simple"


def test_send_ec2_test_email_endpoint_full_mode(setup, monkeypatch):
    """POST /aws/test-email full mode queries live data and returns a summary."""

    def fake_full(recipients, db=None):
        return {"unmatched_found": 2, "account_errors": []}

    monkeypatch.setattr(serve.ec2_unmatched_check, "send_full_test_email", fake_full)

    with serve.app.test_request_context(
        "/aws/test-email",
        method="POST",
        json={"mode": "full", "recipients": ["a@example.com"]},
    ):
        resp = unwrap(serve.send_ec2_unmatched_test_email)()

    assert resp[1] == 200
    payload = json.loads(resp[0])
    assert payload["mode"] == "full"
    assert payload["unmatched_found"] == 2


def test_send_ec2_test_email_endpoint_falls_back_to_saved_recipients(setup, monkeypatch):
    """Falls back to saved settings when no recipients are given in the request."""
    serve.mongo_client["labyrinth"]["settings"].insert_one(
        {"name": "ec2_alert_recipients", "value": "saved@example.com"}
    )

    captured = {}

    def fake_simple(recipients):
        captured["recipients"] = recipients

    monkeypatch.setattr(serve.ec2_unmatched_check, "send_simple_test_email", fake_simple)

    with serve.app.test_request_context(
        "/aws/test-email", method="POST", json={"mode": "simple"}
    ):
        resp = unwrap(serve.send_ec2_unmatched_test_email)()

    assert resp[1] == 200
    assert captured["recipients"] == ["saved@example.com"]


def test_send_ec2_test_email_endpoint_no_recipients(setup):
    """Returns 400 when no recipients are configured or provided."""
    with serve.app.test_request_context(
        "/aws/test-email", method="POST", json={"mode": "simple"}
    ):
        resp = unwrap(serve.send_ec2_unmatched_test_email)()

    assert resp[1] == 400
    assert "No recipients configured" in json.loads(resp[0])["error"]


def test_send_ec2_test_email_endpoint_invalid_mode(setup):
    """Returns 400 for an unsupported mode value."""
    with serve.app.test_request_context(
        "/aws/test-email",
        method="POST",
        json={"mode": "bogus", "recipients": ["a@example.com"]},
    ):
        resp = unwrap(serve.send_ec2_unmatched_test_email)()

    assert resp[1] == 400
    assert "mode must be" in json.loads(resp[0])["error"]


def test_send_ec2_test_email_endpoint_invalid_email_configuration(setup, monkeypatch):
    """Surfaces a 400 when the underlying send raises ValueError."""

    def fake_simple(recipients):
        raise ValueError("bad config")

    monkeypatch.setattr(serve.ec2_unmatched_check, "send_simple_test_email", fake_simple)

    with serve.app.test_request_context(
        "/aws/test-email",
        method="POST",
        json={"mode": "simple", "recipients": ["a@example.com"]},
    ):
        resp = unwrap(serve.send_ec2_unmatched_test_email)()

    assert resp[1] == 400
    assert "Invalid email configuration" in json.loads(resp[0])["error"]
