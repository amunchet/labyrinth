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
    with patch("watcher.requests.request") as post, patch(
        "watcher.open", mock_open(read_data="pw"), create=True
    ):
        post.return_value.ok = True
        started = LabyrinthClient().start_conversation(
            "Grow /var", "OK to extend it?", needs_response=True
        )
    assert started["notified"] is True
    assert post.call_args.args == ("POST", "http://alertmanager:9093/api/v2/alerts")
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


# Armada session callbacks: each ask raises an Armada request, and the human's
# answer finishes it so the agent is told to look again.

CALLBACK = "https://flagship.example/api/session-callback/" + "ab" * 32


@pytest.fixture
def armada():
    """Mocks Armada: every POST answers with a new request id, every DELETE clears."""
    ids = iter("id{}".format(n) for n in range(100))
    with patch("serve.requests.post") as post, patch("serve.requests.delete") as delete:
        post.side_effect = lambda *a, **k: MagicMock(
            **{"json.return_value": {"id": next(ids)}}
        )
        yield post, delete


def _stored(conversation_id):
    return serve.db["labyrinth"]["conversations"].find_one(
        {"conversation_id": conversation_id}
    )


def _question(text="Is tonight OK?"):
    return LabyrinthClient().start_conversation(
        "Rotate certs", text, needs_response=True, armada_callback=CALLBACK
    )


def test_without_armada_nothing_is_sent(db, alerts, uploads, redis_stub, armada):
    post, delete = armada
    client = LabyrinthClient()
    asked = client.start_conversation("Plain", "OK?", needs_response=True)
    assert asked["armada_request"] is False
    staged = client.prepare_deployment(
        {"hosts": ["10.0.0.5"], "playbook": "existing", "become_file": "creds"}
    )
    assert staged["armada_request"] is False
    unwrap(serve.reply_conversation)(asked["conversation_id"], '{"text": "yes"}')
    unwrap(serve.decline_ansible_request)(staged["request_id"], "{}")
    post.assert_not_called()
    delete.assert_not_called()
    assert "armada_callback" not in _stored(asked["conversation_id"])


def test_deploy_without_a_conversation_raises_a_request(db, alerts, uploads, armada):
    post, delete = armada
    staged = LabyrinthClient().prepare_deployment(
        {
            "hosts": ["10.0.0.5"],
            "playbook": "existing",
            "become_file": "creds",
            "notes": "Restart telegraf",
            "armada_callback": CALLBACK,
        }
    )
    assert staged["armada_request"] is True
    post.assert_called_once()
    assert post.call_args.args == (CALLBACK,)
    assert post.call_args.kwargs["json"] == {
        "url": staged["deploy_url"],
        "title": "Labyrinth: Restart telegraf",
        "message": "Restart telegraf",
    }
    assert post.call_args.kwargs["timeout"] == 10
    assert _stored(staged["conversation_id"])["armada_requests"] == [
        {"callback": CALLBACK, "id": "id0"}
    ]


def test_question_then_reply_finishes_the_request(db, alerts, armada):
    post, delete = armada
    asked = _question("x" * 1500)
    assert asked["armada_request"] is True
    assert post.call_args.kwargs["json"]["url"] == asked["url"]
    assert len(post.call_args.kwargs["json"]["message"]) == 1000
    delete.assert_not_called()

    unwrap(serve.reply_conversation)(asked["conversation_id"], '{"text": "yes"}')
    delete.assert_called_once_with(CALLBACK + "/id0", timeout=10)
    assert _stored(asked["conversation_id"])["armada_requests"] == []
    # Nothing outstanding: a second reply sends nothing
    unwrap(serve.reply_conversation)(asked["conversation_id"], '{"text": "again"}')
    delete.assert_called_once()


def test_launch_alone_does_not_finish_but_the_run_result_does(
    db, alerts, uploads, redis_stub, armada
):
    post, delete = armada
    staged = LabyrinthClient().prepare_deployment(
        {
            "hosts": ["10.0.0.5"],
            "playbook": "existing",
            "become_file": "creds",
            "armada_callback": CALLBACK,
        }
    )
    out, status, _ = _deploy(staged["request_id"], vault_password="pw")
    assert status == 200
    delete.assert_not_called()

    _finish_run(
        out["job_id"], staged["conversation_id"], staged["request_id"], _recap()
    )
    delete.assert_called_once_with(CALLBACK + "/id0", timeout=10)


@pytest.mark.parametrize("finish", ["declined", "closed", "agent closed"])
def test_decline_and_close_finish_everything(db, alerts, uploads, armada, finish):
    post, delete = armada
    conversation_id = _question()["conversation_id"]
    staged = LabyrinthClient().prepare_deployment(
        {
            "hosts": ["10.0.0.5"],
            "playbook": "existing",
            "become_file": "creds",
            "conversation_id": conversation_id,
        }
    )
    assert staged["armada_request"] is True
    if finish == "declined":
        unwrap(serve.decline_ansible_request)(staged["request_id"], "{}")
    elif finish == "closed":
        unwrap(serve.close_conversation)(conversation_id, "{}")
    else:
        LabyrinthClient().close_conversation(conversation_id, "Done")
    assert sorted(x.args[0] for x in delete.call_args_list) == [
        CALLBACK + "/id0",
        CALLBACK + "/id1",
    ]
    assert _stored(conversation_id)["armada_requests"] == []


def test_two_questions_with_the_same_id_finish_once(db, alerts, armada):
    post, delete = armada
    post.side_effect = None
    post.return_value.json.return_value = {"id": "same"}
    conversation_id = _question()["conversation_id"]
    LabyrinthClient().send_message(conversation_id, "And this?", True, CALLBACK)
    assert post.call_count == 2
    assert _stored(conversation_id)["armada_requests"] == [
        {"callback": CALLBACK, "id": "same"}
    ]
    unwrap(serve.reply_conversation)(conversation_id, '{"text": "yes"}')
    delete.assert_called_once_with(CALLBACK + "/same", timeout=10)


def test_a_newer_session_takes_over_but_old_requests_finish_where_they_went(
    db, alerts, armada
):
    post, delete = armada
    conversation_id = _question()["conversation_id"]
    newer = CALLBACK.replace("ab" * 32, "cd" * 32)
    LabyrinthClient().send_message(conversation_id, "Still there?", True, newer)
    assert post.call_args.args == (newer,)
    unwrap(serve.reply_conversation)(conversation_id, '{"text": "yes"}')
    assert [x.args[0] for x in delete.call_args_list] == [
        CALLBACK + "/id0",
        newer + "/id1",
    ]


@pytest.mark.parametrize(
    "failure",
    [
        {"side_effect": requests.ConnectionError("down")},
        {
            "return_value": MagicMock(
                **{"raise_for_status.side_effect": requests.HTTPError("500")}
            )
        },
        {"return_value": MagicMock(**{"json.side_effect": ValueError("not json")})},
    ],
)
def test_armada_down_still_records_the_ask(db, alerts, armada, capsys, failure):
    post, delete = armada
    post.side_effect = None
    post.configure_mock(**failure)
    asked = _question()
    assert asked["armada_request"] is False
    found = _conversation(asked["conversation_id"])
    assert found["needs_human"] is True
    assert _stored(asked["conversation_id"]).get("armada_requests") in (None, [])
    assert CALLBACK not in capsys.readouterr().out


def test_failed_finish_still_records_the_answer(db, alerts, armada, capsys):
    post, delete = armada
    delete.side_effect = requests.ConnectionError("down")
    conversation_id = _question()["conversation_id"]
    assert (
        unwrap(serve.reply_conversation)(conversation_id, '{"text": "yes"}')[1] == 200
    )
    assert _conversation(conversation_id)["messages"][-1]["kind"] == "reply"
    assert CALLBACK not in capsys.readouterr().out


def test_callback_is_never_returned(db, alerts, armada):
    conversation_id = _question()["conversation_id"]
    client = LabyrinthClient()
    for shown in (
        unwrap(serve.get_conversation)(conversation_id)[0],
        unwrap(serve.list_conversations)("")[0],
        unwrap(serve.list_conversations)("waiting")[0],
        json.dumps(client.check_response(conversation_id, 0)),
    ):
        assert "session-callback" not in shown and "armada_requests" not in shown


@pytest.mark.parametrize(
    "callback",
    [
        "",
        "https://flagship.example/api/other/" + "ab" * 32,
        "https://user@flagship.example/api/session-callback/" + "ab" * 32,
        CALLBACK + "/extra",
        "ftp://flagship.example/api/session-callback/" + "ab" * 32,
    ],
)
def test_invalid_callback_is_ignored(db, alerts, armada, callback):
    post, delete = armada
    asked = LabyrinthClient().start_conversation(
        "Odd", "OK?", needs_response=True, armada_callback=callback
    )
    assert asked["armada_request"] is False
    post.assert_not_called()
    assert "armada_callback" not in _stored(asked["conversation_id"])


def test_racing_asks_both_keep_their_request(db, alerts, armada):
    """An ask stored while another was being stored must not be lost."""
    conversation_id = _question()["conversation_id"]
    collection_type = type(serve.db["labyrinth"]["conversations"])
    real_update_one = collection_type.update_one
    raced = []

    def update_one_after_race(self, filt, update, *args, **kwargs):
        if "armada_requests" in filt and not raced:
            raced.append(True)
            # A parallel ask stores its request between this read and write
            real_update_one(
                self,
                {"conversation_id": conversation_id},
                {"$set": {"armada_requests": [{"callback": CALLBACK, "id": "other"}]}},
            )
        return real_update_one(self, filt, update, *args, **kwargs)

    serve.db["labyrinth"]["conversations"].update_one(
        {"conversation_id": conversation_id}, {"$set": {"armada_requests": []}}
    )
    with patch.object(collection_type, "update_one", update_one_after_race):
        LabyrinthClient().send_message(conversation_id, "More?", True, CALLBACK)
    assert _stored(conversation_id)["armada_requests"] == [
        {"callback": CALLBACK, "id": "other"},
        {"callback": CALLBACK, "id": "id1"},
    ]
