"""Skills exposed by the Labyrinth chat assistant.

Skills are deliberately small capability bundles rather than model prompts. The
prompt remains configurable in the management database, while this registry
controls which server-side tools a session may call.
"""

SKILLS = [
    {
        "id": "network_inventory",
        "name": "Network inventory",
        "description": "Inspect known hosts, services, and recent metrics.",
        "tools": ["list_hosts", "get_host", "list_services", "read_metrics"],
        "default_enabled": True,
    },
    {
        "id": "host_diagnostics",
        "name": "Safe host diagnostics",
        "description": "Run the fixed, read-only diagnostic commands on a host.",
        "tools": ["run_diagnostic_command"],
        "default_enabled": True,
    },
    {
        "id": "ansible_draft",
        "name": "Ansible solution drafts",
        "description": "Validate and stage an Ansible playbook for human review.",
        "tools": ["propose_playbook"],
        "default_enabled": True,
    },
]

SKILL_BY_ID = {skill["id"]: skill for skill in SKILLS}
DEFAULT_SKILL_IDS = [skill["id"] for skill in SKILLS if skill["default_enabled"]]


def normalize_skill_ids(skill_ids):
    """Return known, unique skill ids while preserving registry order."""
    requested = set(skill_ids or DEFAULT_SKILL_IDS)
    return [skill["id"] for skill in SKILLS if skill["id"] in requested]
