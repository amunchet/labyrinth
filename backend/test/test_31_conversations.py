"""
Agent conversations: an agent (through the MCP client) and a human take turns
in one recorded thread - questions, staged deployments, replies, and the
results of the runs the human launched.
"""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest
import requests

import serve
from ai.mcp.client import LabyrinthClient
from common.test import unwrap

GENERATED = "- hosts: all\n  tasks:\n    - ping:\n"


@pytest.fixture
def db():
    collections = [
        serve.db["labyrinth"][name]
        for name in ("conversations", "ansible_requests", "ansible_runs")
    ]
    for collection in collections:
        collection.delete_many({})
    yield serve.db["labyrinth"]["conversations"]
    for collection in collections:
        collection.delete_many({})


@pytest.fixture
def alerts(monkeypatch):
    """Records the Alertmanager alerts raised when the human is needed."""
    monkeypatch.setenv("LABYRINTH_URL", "https://lab.example")
    with patch("serve.watcher.send_alert") as send:
        send.return_value.ok = True
        yield send


@pytest.fixture
def uploads(monkeypatch):
    """Pretend /src/uploads holds two become files and one playbook."""
    real_listdir = serve.os.listdir
    files = {
        "/src/uploads/become": ["creds.yml", "other.yml"],
        "/src/uploads/ansible": ["existing.yml"],
    }
    monkeypatch.setattr(
        serve.os, "listdir", lambda p: files[p] if p in files else real_listdir(p)
    )


@pytest.fixture
def redis_stub():
    with patch("serve.redis.Redis"):
        yield


def _conversation(conversation_id):
    return json.loads(unwrap(serve.get_conversation)(conversation_id)[0])


def _deploy(request_id, **data):
    with patch("serve.Process") as process:
        out, status = unwrap(serve.deploy_ansible_request)(request_id, json.dumps(data))
    return out, status, process


def _finish_run(job_id, conversation_id, request_id, recap):
    """Run run_ansible_background with Ansible mocked out to end on `recap`."""
    thread = MagicMock()
    thread.is_alive.side_effect = [True, False]
    runner = MagicMock()
    runner.events = [recap]
    with patch(
        "serve.ansible_helper.run_ansible", return_value=("/tmp/RUN_X", "pb")
    ), patch("serve.ansible_runner.run_async", return_value=(thread, runner)), patch(
        "serve.os.listdir", return_value=[]
    ), patch(
        "serve.shutil.rmtree"
    ), patch(
        "serve.time.sleep"
    ):
        serve.run_ansible_background(
            job_id,
            {
                "hosts": ["10.0.0.5"],
                "playbook": "pb",
                "vault_password": "pw",
                "become_file": "creds",
                "request_id": request_id,
                "conversation_id": conversation_id,
            },
        )


def _recap(failures=None):
    return {
        "stdout": "PLAY RECAP",
        "event": "playbook_on_stats",
        "event_data": {"ok": {"10.0.0.5": 2}, "failures": failures or {}, "dark": {}},
    }


def test_question_flags_the_human_until_they_reply(db, alerts, redis_stub):
    client = LabyrinthClient()
    started = client.start_conversation(
        "Rotate nginx certs", "Is tonight OK for a reload?", needs_response=True
    )
    conversation_id = started["conversation_id"]
    assert started["url"] == "https://lab.example/conversations/" + conversation_id
    assert started["notified"] is True

    # The alert points at the conversation, where the human can answer
    alerts.assert_called_once()
    assert alerts.call_args.args[1:] == (
        "Rotate nginx certs",
        "{}/{}".format(conversation_id, started["message_id"]),
    )
    assert alerts.call_args.kwargs["url"] == started["url"]

    waiting = json.loads(unwrap(serve.list_conversations)("waiting")[0])
    assert [x["conversation_id"] for x in waiting] == [conversation_id]
    assert waiting[0]["last_message"]["kind"] == "question"
    assert client.check_response(conversation_id)["answered"] is False

    assert (
        unwrap(serve.reply_conversation)(
            conversation_id, json.dumps({"text": " Yes, after 9pm "})
        )[1]
        == 200
    )
    found = _conversation(conversation_id)
    assert found["pending"] == []
    assert found["needs_human"] is False
    assert json.loads(unwrap(serve.list_conversations)("waiting")[0]) == []

    state = client.check_response(conversation_id)
    assert state["answered"] is True
    assert [(m["author"], m["text"]) for m in state["new_messages"]] == [
        ("human", "Yes, after 9pm")
    ]
    # Waiting from the reply onwards finds nothing new
    assert (
        client.check_response(conversation_id, state["message_count"])["answered"]
        is False
    )


def test_staged_deployment_round_trip(db, alerts, uploads, redis_stub):
    """Agent stages, human launches, the agent wakes only on the run's result."""
    client = LabyrinthClient()
    conversation_id = client.start_conversation("Patch web01")["conversation_id"]
    staged = client.prepare_deployment(
        {
            "hosts": ["10.0.0.5"],
            "playbook": "ai_patch",
            "become_file": "",
            "playbook_content": GENERATED,
            "notes": "Apply the security updates",
            "conversation_id": conversation_id,
        }
    )
    request_id = staged["request_id"]
    assert staged["conversation_id"] == conversation_id
    assert staged["deploy_url"] == "https://lab.example/deploy?request=" + request_id
    assert alerts.call_args.kwargs["url"] == staged["deploy_url"]
    assert _conversation(conversation_id)["pending"] == [
        {"type": "deploy", "id": request_id}
    ]

    # The agent left the become file to the human, who must pick one
    assert _deploy(request_id, vault_password="pw")[1] == 482
    assert _deploy(request_id, vault_password="pw", become_file="nope")[1] == 483
    with patch(
        "serve.ansible_helper.persist_reviewed_playbook",
        return_value=[True, b"", b""],
    ) as persist:
        out, status, process = _deploy(
            request_id, vault_password="pw", become_file="other.yml"
        )
    assert status == 200
    assert persist.call_args.args[2] == "other"
    job = process.call_args.kwargs["args"][1]
    assert (job["become_file"], job["conversation_id"]) == ("other", conversation_id)

    # Launching settles the request, but the agent keeps waiting for the result
    found = _conversation(conversation_id)
    assert found["pending"] == [] and found["needs_human"] is False
    assert found["messages"][-1]["kind"] == "launched"
    state = client.check_response(conversation_id)
    assert state["answered"] is False
    assert state["runs_in_progress"] == [out["job_id"]]

    _finish_run(out["job_id"], conversation_id, request_id, _recap({"10.0.0.5": 1}))
    state = client.check_response(conversation_id)
    assert state["answered"] is True
    assert state["runs_in_progress"] == []
    result = state["new_messages"][-1]
    assert (result["author"], result["kind"], result["outcome"]) == (
        "system",
        "run",
        "failed",
    )
    assert result["job_id"] == out["job_id"]
    assert result["stats"]["failures"] == {"10.0.0.5": 1}

    # The history ties the run to the deployment it came from
    runs = _conversation(conversation_id)["requests"][request_id]["runs"]
    assert [(r["job_id"], r["outcome"]) for r in runs] == [(out["job_id"], "failed")]


def test_staging_without_a_conversation_starts_one(db, alerts, uploads):
    out, status = unwrap(serve.create_ansible_request)(
        json.dumps(
            {
                "hosts": ["10.0.0.5"],
                "playbook": "existing",
                "become_file": "creds",
                "notes": "Restart telegraf",
            }
        )
    )
    assert status == 200
    found = _conversation(out["conversation_id"])
    assert found["title"] == "Restart telegraf"
    assert found["messages"][0]["request_id"] == out["request_id"]
    assert found["requests"][out["request_id"]]["become_file"] == "creds"

    # An unknown conversation is refused before anything is staged
    assert (
        unwrap(serve.create_ansible_request)(
            json.dumps(
                {
                    "hosts": ["10.0.0.5"],
                    "playbook": "existing",
                    "conversation_id": "missing",
                }
            )
        )[1]
        == 404
    )
    assert serve.db["labyrinth"]["ansible_requests"].count_documents({}) == 1


def test_decline_tells_the_agent(db, alerts, uploads):
    client = LabyrinthClient()
    staged = client.prepare_deployment(
        {"hosts": ["10.0.0.5"], "playbook": "existing", "become_file": "creds"}
    )
    conversation_id = staged["conversation_id"]

    assert (
        unwrap(serve.decline_ansible_request)(
            staged["request_id"], json.dumps({"text": "Not during the shift"})
        )[1]
        == 200
    )
    state = client.check_response(conversation_id)
    assert state["answered"] is True
    assert state["waiting_on_human"] == []
    assert state["new_messages"][-1]["kind"] == "declined"
    assert state["new_messages"][-1]["text"] == "Not during the shift"
    assert _conversation(conversation_id)["requests"][staged["request_id"]][
        "declined_at"
    ]

    assert unwrap(serve.decline_ansible_request)("missing", "{}")[1] == 404


def test_close_and_reopen(db, alerts, uploads, redis_stub):
    client = LabyrinthClient()
    conversation_id = client.start_conversation(
        "Cleanup", "Delete the old snapshots?", needs_response=True
    )["conversation_id"]

    assert (
        unwrap(serve.close_conversation)(
            conversation_id, json.dumps({"text": "Done by hand"})
        )[1]
        == 200
    )
    found = _conversation(conversation_id)
    assert (found["status"], found["pending"]) == ("closed", [])
    assert client.check_response(conversation_id)["answered"] is True

    # A late run result does not reopen it; the agent speaking again does
    serve.post_conversation_message(conversation_id, "system", "run", "Run failed")
    assert _conversation(conversation_id)["status"] == "closed"
    client.send_message(conversation_id, "One more thing")
    assert _conversation(conversation_id)["status"] == "open"

    client.close_conversation(conversation_id, "All done")
    assert _conversation(conversation_id)["messages"][-1]["author"] == "agent"
    assert client.check_response(conversation_id)["status"] == "closed"


def test_alertmanager_down_still_records_the_question(db, alerts):
    alerts.side_effect = requests.ConnectionError("down")
    client = LabyrinthClient()
    started = client.start_conversation("Disk", "Grow /var?", needs_response=True)
    assert started["notified"] is False
    assert _conversation(started["conversation_id"])["needs_human"] is True


def test_bad_input_is_refused(db, alerts):
    client = LabyrinthClient()
    conversation_id = client.start_conversation("Empty", " ")["conversation_id"]
    # Blank titles and first messages are left out rather than stored empty
    assert _conversation(conversation_id)["messages"] == []
    assert client.start_conversation("  ")["conversation_id"]
    assert serve.db["labyrinth"]["conversations"].find_one({"title": "Untitled"})

    assert unwrap(serve.reply_conversation)(conversation_id, '{"text": " "}')[1] == 482
    assert unwrap(serve.reply_conversation)("missing", '{"text": "hi"}')[1] == 404
    assert unwrap(serve.close_conversation)("missing", "{}")[1] == 404
    assert unwrap(serve.get_conversation)("missing")[1] == 404
    assert unwrap(serve.list_conversations)("bogus")[1] == 404
    with pytest.raises(ValueError):
        client.send_message(conversation_id, "  ")
    with pytest.raises(ValueError):
        client.send_message("missing", "hi")
    with pytest.raises(ValueError):
        client.close_conversation("missing")
    with pytest.raises(RuntimeError, match="404"):
        client.check_response("missing")
    # A plain message never alerts anyone
    client.send_message(conversation_id, "FYI: starting")
    alerts.assert_not_called()
    listed = client.list_conversations()
    assert listed[0]["conversation_id"] == conversation_id
    assert listed[0]["message_count"] == 1
    assert client.list_conversations(waiting_only=True) == []


def test_alert_links_to_the_ask(db, monkeypatch):
    """The real alert payload, only HTTP mocked: one alert per ask, linking to it."""
    monkeypatch.setenv("LABYRINTH_URL", "https://lab.example")
    with patch("watcher.requests.post") as post, patch(
        "watcher.open", mock_open(read_data="pw"), create=True
    ):
        post.return_value.ok = True
        started = LabyrinthClient().start_conversation(
            "Grow /var", "OK to extend it?", needs_response=True
        )
    assert started["notified"] is True
    assert post.call_args.args == ("http://alertmanager:9093/api/v2/alerts",)
    assert post.call_args.kwargs["timeout"] == 10
    (alert,) = json.loads(post.call_args.kwargs["data"])
    assert alert["generatorURL"] == started["url"]
    assert alert["labels"]["instance"] == "{}/{}".format(
        started["conversation_id"], started["message_id"]
    )
    assert alert["annotations"]["summary"] == "OK to extend it?"


def test_simultaneous_posts_keep_each_others_changes(db, alerts):
    """A post that read the conversation before another one landed must not undo it."""
    conversation_id = LabyrinthClient().start_conversation("Race")["conversation_id"]
    collection_type = type(serve.db["labyrinth"]["conversations"])
    real_find_one = collection_type.find_one
    raced = []

    def find_one_then_race(self, *args, **kwargs):
        found = real_find_one(self, *args, **kwargs)
        if not raced:
            raced.append(True)
            # A parallel tool call lands between this read and its write
            serve.post_conversation_message(conversation_id, "agent", "question", "B?")
        return found

    with patch.object(collection_type, "find_one", find_one_then_race):
        serve.post_conversation_message(conversation_id, "agent", "question", "A?")

    found = _conversation(conversation_id)
    assert [m["text"] for m in found["messages"]] == ["B?", "A?"]
    assert len(found["pending"]) == 2
    assert found["needs_human"] is True

    # A late run result neither revives answered questions nor reopens
    unwrap(serve.close_conversation)(conversation_id, "{}")
    serve.post_conversation_message(conversation_id, "system", "run", "Run failed")
    found = _conversation(conversation_id)
    assert (found["status"], found["pending"], found["needs_human"]) == (
        "closed",
        [],
        False,
    )
