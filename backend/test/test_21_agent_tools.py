#!/usr/bin/env python3
"""
Tests for ai/agent_tools.py - the tool registry + single dispatch() entry
point the agentic loop calls to execute tools by name.
"""
from unittest.mock import patch

from ai import agent_tools


def test_tool_defs_cover_expected_tools():
    names = {t.name for t in agent_tools.TOOL_DEFS}
    assert names == {
        "list_hosts",
        "get_host",
        "read_metrics",
        "list_services",
        "run_diagnostic_command",
        "propose_playbook",
    }


@patch.object(agent_tools.client, "list_hosts")
def test_dispatch_list_hosts(mock_list_hosts):
    mock_list_hosts.return_value = [{"mac": "aa:bb"}]
    result = agent_tools.dispatch("sess1", "list_hosts", {})
    assert result == {"hosts": [{"mac": "aa:bb"}]}


@patch.object(agent_tools.client, "get_host")
def test_dispatch_get_host(mock_get_host):
    mock_get_host.return_value = {"mac": "aa:bb", "ip": "10.0.0.5"}
    result = agent_tools.dispatch("sess1", "get_host", {"host_key": "10.0.0.5"})
    assert result == {"host": {"mac": "aa:bb", "ip": "10.0.0.5"}}
    mock_get_host.assert_called_once_with("10.0.0.5")


@patch.object(agent_tools.client, "get_metrics")
def test_dispatch_read_metrics(mock_get_metrics):
    mock_get_metrics.return_value = {"metrics": []}
    result = agent_tools.dispatch(
        "sess1", "read_metrics", {"host_key": "10.0.0.5", "count": 10}
    )
    assert result == {"metrics": {"metrics": []}}
    mock_get_metrics.assert_called_once_with("10.0.0.5", "", 10)


@patch.object(agent_tools.client, "list_services")
def test_dispatch_list_services(mock_list_services):
    mock_list_services.return_value = [{"name": "check_cpu"}]
    result = agent_tools.dispatch("sess1", "list_services", {"include_full": True})
    assert result == {"services": [{"name": "check_cpu"}]}
    mock_list_services.assert_called_once_with(include_full=True)


def test_dispatch_unknown_tool_returns_error_not_raise():
    result = agent_tools.dispatch("sess1", "delete_everything", {})
    assert "error" in result


def test_dispatch_missing_required_field_returns_error_not_raise():
    # get_host requires host_key - a hallucinated/malformed tool call shouldn't
    # crash the agentic loop, it should come back as a tool error the model can see.
    result = agent_tools.dispatch("sess1", "get_host", {})
    assert "error" in result


@patch("ai.agent_tools.diagnostic_tools.run_diagnostic_command")
@patch("ai.agent_tools.chat_store.get_session")
def test_dispatch_run_diagnostic_command(mock_get_session, mock_run_diag):
    mock_get_session.return_value = {
        "become_file": "vault",
        "vault_password": "secret",
        "ssh_key": "",
    }
    mock_run_diag.return_value = {"status": "successful", "rc": 0, "stdout": "ok"}

    result = agent_tools.dispatch(
        "sess1",
        "run_diagnostic_command",
        {"host": "10.0.0.5", "command_name": "disk_usage"},
    )

    assert result == {"status": "successful", "rc": 0, "stdout": "ok"}
    mock_run_diag.assert_called_once_with(
        "10.0.0.5",
        "disk_usage",
        "",
        become_file="vault",
        vault_password="secret",
        ssh_key="",
    )


@patch("ai.agent_tools.chat_store.get_session")
def test_dispatch_run_diagnostic_command_missing_session(mock_get_session):
    mock_get_session.return_value = None
    result = agent_tools.dispatch(
        "sess-missing",
        "run_diagnostic_command",
        {"host": "10.0.0.5", "command_name": "disk_usage"},
    )
    assert "error" in result


@patch("ai.agent_tools.chat_store.set_draft")
@patch("ai.agent_tools.ansible_helper.check_file")
def test_dispatch_propose_playbook_valid(mock_check_file, mock_set_draft):
    mock_check_file.return_value = [True, b"stdout ok", b""]

    result = agent_tools.dispatch(
        "sess1",
        "propose_playbook",
        {
            "yaml": "---\n- hosts: all\n  tasks: []\n",
            "filename": "fix_disk",
            "description": "Clears old logs to free disk space.",
        },
    )

    assert result["valid"] is True
    assert result["draft"]["filename"] == "fix_disk"
    mock_check_file.assert_called_once_with(
        "fix_disk", "ansible", raw="---\n- hosts: all\n  tasks: []\n", persist=False
    )
    mock_set_draft.assert_called_once_with(
        "sess1",
        {
            "yaml": "---\n- hosts: all\n  tasks: []\n",
            "filename": "fix_disk",
            "description": "Clears old logs to free disk space.",
        },
    )


@patch("ai.agent_tools.chat_store.set_draft")
@patch("ai.agent_tools.ansible_helper.check_file")
def test_dispatch_propose_playbook_invalid_yaml_no_draft_stored(
    mock_check_file, mock_set_draft
):
    mock_check_file.return_value = [False, b"", b"syntax error"]

    result = agent_tools.dispatch(
        "sess1",
        "propose_playbook",
        {"yaml": "not valid", "filename": "broken", "description": "d"},
    )

    assert result["valid"] is False
    assert result["stderr"] == "syntax error"
    mock_set_draft.assert_not_called()
