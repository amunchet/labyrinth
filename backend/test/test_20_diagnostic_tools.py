#!/usr/bin/env python3
"""
Tests for the allowlisted diagnostic command builder used by the AI chat
agent's run_diagnostic_command tool - the model only ever supplies an enum
`command_name` + a regex-validated `target`, never a shell string.
"""
from unittest.mock import patch

import pytest

from ai import diagnostic_tools


def test_build_argv_no_target_needed():
    assert diagnostic_tools.build_argv("disk_usage") == ["df", "-h"]
    assert diagnostic_tools.build_argv("docker_ps") == ["docker", "ps", "-a"]
    assert diagnostic_tools.build_argv("memory_usage") == ["free", "-m"]


def test_build_argv_with_valid_target():
    assert diagnostic_tools.build_argv("docker_inspect", "my_container") == [
        "docker",
        "inspect",
        "my_container",
    ]
    assert diagnostic_tools.build_argv("docker_logs", "my_container") == [
        "docker",
        "logs",
        "--tail",
        "200",
        "my_container",
    ]


def test_build_argv_unknown_command_rejected():
    with pytest.raises(ValueError):
        diagnostic_tools.build_argv("rm_rf_root")


def test_build_argv_missing_target_rejected():
    with pytest.raises(ValueError):
        diagnostic_tools.build_argv("docker_inspect", "")


@pytest.mark.parametrize(
    "bad_target",
    [
        "; rm -rf /",
        "$(reboot)",
        "a && b",
        "name with spaces",
        "`whoami`",
        "a" * 200,
    ],
)
def test_build_argv_shell_metacharacters_rejected(bad_target):
    with pytest.raises(ValueError):
        diagnostic_tools.build_argv("docker_inspect", bad_target)


@patch("ai.diagnostic_tools.ansible_helper.run_adhoc")
def test_run_diagnostic_command_dispatches_to_run_adhoc(mock_run_adhoc):
    mock_run_adhoc.return_value = {"status": "successful", "rc": 0, "stdout": "ok"}

    result = diagnostic_tools.run_diagnostic_command(
        "10.0.0.5",
        "disk_usage",
        become_file="vault",
        vault_password="secret",
        ssh_key="",
    )

    assert result == {"status": "successful", "rc": 0, "stdout": "ok"}
    mock_run_adhoc.assert_called_once_with(
        ["10.0.0.5"], ["df", "-h"], "secret", "vault", ssh_key_file=""
    )


@patch("ai.diagnostic_tools.ansible_helper.run_adhoc")
def test_run_diagnostic_command_rejects_before_touching_ansible(mock_run_adhoc):
    with pytest.raises(ValueError):
        diagnostic_tools.run_diagnostic_command(
            "10.0.0.5",
            "docker_inspect",
            target="bad; rm -rf /",
            become_file="vault",
            vault_password="secret",
        )

    mock_run_adhoc.assert_not_called()
