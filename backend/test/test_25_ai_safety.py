from ai import agent_tools
from ansible_helper import validate_ai_playbook


def test_ai_playbook_requires_controller_inventory_group():
    assert validate_ai_playbook("- hosts: 10.0.0.5\n  tasks: []\n")
    assert validate_ai_playbook(
        "- hosts: all\n  vars_files: [secret.yml]\n  tasks: []\n"
    )


def test_ai_playbook_rejects_cleartext_passwords():
    error = validate_ai_playbook(
        "- hosts: clients\n  vars:\n    ansible_become_password: cleartext\n  tasks: []\n"
    )
    assert "cleartext" in error


def test_ai_playbook_accepts_generic_safe_play():
    assert (
        validate_ai_playbook(
            "- hosts: clients\n  gather_facts: false\n  tasks:\n    - command: df -h\n"
        )
        is None
    )


def test_ai_playbook_rejects_configured_target_host():
    error = validate_ai_playbook(
        "- hosts: clients\n  tasks:\n    - debug: {msg: 10.0.0.5}\n",
        forbidden_hosts=["10.0.0.5"],
    )
    assert "target hosts" in error


def test_ai_playbook_rejects_invalid_yaml():
    error = validate_ai_playbook("- {invalid yaml [unclosed")
    assert "Invalid YAML" in error


def test_ai_playbook_rejects_empty_playbook():
    error = validate_ai_playbook("")
    assert error is not None


def test_ai_playbook_rejects_non_dict_plays():
    # A YAML document that is a sequence but contains non-dict items
    error = validate_ai_playbook("- plain string item\n")
    assert error is not None


def test_ai_playbook_single_dict_document():
    # A single dict document (not wrapped in a list) goes through the elif branch
    # It's treated as a single play; hosts: clients is allowed so result is None
    result = validate_ai_playbook("hosts: clients\ntasks: []\n")
    assert result is None


def test_target_hosts_are_excluded_from_inventory_context(monkeypatch):
    monkeypatch.setattr(
        agent_tools.chat_store, "get_session", lambda _: {"target_hosts": ["10.0.0.5"]}
    )
    monkeypatch.setattr(
        agent_tools.client,
        "list_hosts",
        lambda: [{"ip": "10.0.0.5"}, {"ip": "10.0.0.6"}],
    )

    assert agent_tools.dispatch("session", "list_hosts", {}) == {
        "hosts": [{"ip": "10.0.0.6"}]
    }
    assert "error" in agent_tools.dispatch(
        "session", "get_host", {"host_key": "10.0.0.5"}
    )
