"""
Allowlisted, read-only diagnostic commands the chat agent can run against a live
host. The model only ever supplies a closed `command_name` enum plus an optional
`target` identifier (validated against TARGET_RE) - it never supplies or influences
a shell string. Commands run via Ansible's `command` module (no shell interpolation)
through `ansible_helper.run_adhoc`.
"""

import re

import ansible_helper

TARGET_RE = re.compile(r"^[a-zA-Z0-9_.:-]{1,128}$")

# Each value is an argv template; "{target}" entries are filled in from a
# regex-validated `target` argument. Every command here is read-only.
ALLOWED_COMMANDS = {
    "disk_usage": ["df", "-h"],
    "docker_ps": ["docker", "ps", "-a"],
    "docker_inspect": ["docker", "inspect", "{target}"],
    "docker_logs": ["docker", "logs", "--tail", "200", "{target}"],
    "journalctl": ["journalctl", "-u", "{target}", "-n", "200", "--no-pager"],
    "systemctl_status": ["systemctl", "status", "{target}", "--no-pager"],
    "memory_usage": ["free", "-m"],
}


def _needs_target(template):
    return any("{target}" in part for part in template)


def build_argv(command_name, target=""):
    """Validate command_name/target and return the fixed argv to execute."""
    if command_name not in ALLOWED_COMMANDS:
        raise ValueError(f"Unknown diagnostic command: {command_name}")

    template = ALLOWED_COMMANDS[command_name]

    if _needs_target(template):
        if not target or not TARGET_RE.match(target):
            raise ValueError(
                f"A valid target is required for diagnostic command '{command_name}'"
            )
        return [part.format(target=target) for part in template]

    return list(template)


def run_diagnostic_command(
    host, command_name, target="", *, become_file, vault_password, ssh_key=""
):
    """Validate + execute an allowlisted diagnostic command on `host`."""
    argv = build_argv(command_name, target)
    return ansible_helper.run_adhoc(
        [host], argv, vault_password, become_file, ssh_key_file=ssh_key
    )
