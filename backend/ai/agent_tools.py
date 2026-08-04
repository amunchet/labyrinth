"""
Tool registry + single dispatch entry point for the AI chat agentic loop.

Wraps the shared `LabyrinthClient` (read-only host/service/metric tools),
the allowlisted diagnostic-command runner, and `propose_playbook` (which
stages a draft for human review rather than deploying anything).
"""

import ansible_helper

from ai import chat_store
from ai import diagnostic_tools
from ai.skills import SKILLS
from ai.mcp.client import LabyrinthClient
from ai.providers.base import ToolDef

client = LabyrinthClient()


TOOL_DEFS = [
    ToolDef(
        name="list_hosts",
        description="List all known hosts.",
        input_schema={"type": "object", "properties": {}},
    ),
    ToolDef(
        name="get_host",
        description="Fetch a single host by MAC address or IP.",
        input_schema={
            "type": "object",
            "properties": {"host_key": {"type": "string"}},
            "required": ["host_key"],
        },
    ),
    ToolDef(
        name="read_metrics",
        description="Read recent Telegraf metrics for a host (optionally filtered by service).",
        input_schema={
            "type": "object",
            "properties": {
                "host_key": {"type": "string"},
                "service": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["host_key"],
        },
    ),
    ToolDef(
        name="list_services",
        description="List service/check definitions.",
        input_schema={
            "type": "object",
            "properties": {"include_full": {"type": "boolean"}},
        },
    ),
    ToolDef(
        name="run_diagnostic_command",
        description=(
            "Run a safe, allowlisted read-only diagnostic command on a live host "
            "(disk usage, docker status, logs, service status). Cannot run arbitrary shell."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "command_name": {
                    "type": "string",
                    "enum": list(diagnostic_tools.ALLOWED_COMMANDS.keys()),
                },
                "target": {
                    "type": "string",
                    "description": "Container/unit name, required by some command_names",
                },
            },
            "required": ["host", "command_name"],
        },
    ),
    ToolDef(
        name="propose_playbook",
        description=(
            "Stage a draft Ansible playbook for human review. Validates the YAML "
            "with `ansible-playbook --check` but does NOT deploy or persist it."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "yaml": {"type": "string"},
                "filename": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["yaml", "filename", "description"],
        },
    ),
]


def tool_defs_for_session(session):
    """Return only the tools enabled by the session's selected skills."""
    skill_ids = set(session.get("skill_ids") or [])
    if not skill_ids:
        return TOOL_DEFS
    enabled = {
        tool
        for skill in SKILLS
        if skill["id"] in skill_ids
        for tool in skill["tools"]
    }
    return [tool for tool in TOOL_DEFS if tool.name in enabled]


def _decode(value):
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _target_hosts(session):
    return {
        str(host).strip().lower()
        for host in (session.get("target_hosts") or [])
        if str(host).strip()
    }


def _is_target_host(session, host):
    return str(host or "").strip().lower() in _target_hosts(session)


def _session_or_empty(session_id):
    try:
        return chat_store.get_session(session_id) or {}
    except Exception:
        return {}


def _run_diagnostic(session_id, tool_input):
    session = _session_or_empty(session_id)
    if not session:
        raise ValueError("Chat session not found or expired")
    if _is_target_host(session, tool_input.get("host")):
        return {"error": "Deployment target hosts are excluded from assistant diagnostics."}

    result = diagnostic_tools.run_diagnostic_command(
        tool_input["host"],
        tool_input["command_name"],
        tool_input.get("target", ""),
        become_file=session.get("become_file", ""),
        vault_password=session.get("vault_password", ""),
        ssh_key=session.get("ssh_key", ""),
    )
    return result


def _propose_playbook(session_id, tool_input):
    yaml_content = tool_input["yaml"]
    filename = tool_input["filename"]
    description = tool_input["description"]

    retval, stdout, stderr = ansible_helper.check_file(
        filename, "ansible", raw=yaml_content, persist=False
    )

    if not retval:
        return {
            "valid": False,
            "stdout": _decode(stdout),
            "stderr": _decode(stderr),
        }

    session = _session_or_empty(session_id)
    scope_error = ansible_helper.validate_ai_playbook(
        yaml_content, forbidden_hosts=session.get("target_hosts", [])
    )
    if scope_error:
        return {"valid": False, "stdout": "", "stderr": scope_error}

    draft = {"yaml": yaml_content, "filename": filename, "description": description}
    chat_store.set_draft(session_id, draft)
    return {"valid": True, "draft": draft}


def dispatch(session_id, name, tool_input):
    """Single entry point the agentic loop calls to execute any tool by name."""
    tool_input = tool_input or {}
    try:
        session = _session_or_empty(session_id)
        if session.get("skill_ids"):
            allowed_tools = {tool.name for tool in tool_defs_for_session(session)}
            if name not in allowed_tools:
                return {"error": "This skill is not enabled for the session."}
        if name == "list_hosts":
            excluded = _target_hosts(session)
            hosts = [
                host
                for host in client.list_hosts()
                if not excluded.intersection(
                    {
                        str(host.get("ip", "")).strip().lower(),
                        str(host.get("mac", "")).strip().lower(),
                        str(host.get("name", "")).strip().lower(),
                    }
                )
            ]
            return {"hosts": hosts}
        if name == "get_host":
            if _is_target_host(session, tool_input.get("host_key")):
                return {"error": "Deployment target hosts are excluded from assistant context."}
            return {"host": client.get_host(tool_input["host_key"])}
        if name == "read_metrics":
            if _is_target_host(session, tool_input.get("host_key")):
                return {"error": "Deployment target hosts are excluded from assistant context."}
            return {
                "metrics": client.get_metrics(
                    tool_input["host_key"],
                    tool_input.get("service", ""),
                    tool_input.get("count", 50),
                )
            }
        if name == "list_services":
            return {
                "services": client.list_services(
                    include_full=tool_input.get("include_full", False)
                )
            }
        if name == "run_diagnostic_command":
            return _run_diagnostic(session_id, tool_input)
        if name == "propose_playbook":
            return _propose_playbook(session_id, tool_input)
        return {"error": f"Unknown tool: {name}"}
    except Exception:
        return {"error": "Tool execution failed"}
