"""
Ansible run history (Mongo `ansible_runs`) and staged deployment requests
(`ansible_requests`) that the MCP server reads back and the Deploy page deep-links to.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
import serve
from common.test import unwrap


class FakeRedis:
    """Minimal Redis stand-in for the hash/list calls the runner makes."""

    def __init__(self):
        self.h = {}
        self.l = {}

    def hset(self, name, key, value):
        self.h.setdefault(name, {})[key] = str(value).encode()

    def hget(self, name, key):
        return self.h.get(name, {}).get(key)

    def rpush(self, name, value):
        self.l.setdefault(name, []).append(str(value).encode())

    def lrange(self, name, start, end):
        return self.l.get(name, [])[start:]


@pytest.fixture
def db():
    runs = serve.mongo_client["labyrinth"]["ansible_runs"]
    requests = serve.mongo_client["labyrinth"]["ansible_requests"]
    runs.delete_many({})
    requests.delete_many({})
    yield runs, requests
    runs.delete_many({})
    requests.delete_many({})


@pytest.fixture
def fake_redis():
    fake = FakeRedis()
    with patch("serve.redis.Redis", return_value=fake):
        yield fake


@pytest.fixture
def uploads(monkeypatch):
    """Pretend /src/uploads holds one become file and one playbook."""
    real_listdir = serve.os.listdir
    files = {
        "/src/uploads/become": ["creds.yml"],
        "/src/uploads/ansible": ["existing.yml"],
    }
    monkeypatch.setattr(
        serve.os, "listdir", lambda p: files[p] if p in files else real_listdir(p)
    )


def _event(stdout, event="verbose", **event_data):
    return {"stdout": stdout, "event": event, "event_data": event_data}


def _run(job_id, events, run_dir="/tmp/RUN_DIR_X"):
    """Run run_ansible_background with ansible itself mocked out to emit `events`."""
    thread = MagicMock()
    thread.is_alive.side_effect = [True, False]
    runner = MagicMock()
    runner.events = events
    with patch("serve.ansible_helper.run_ansible", return_value=(run_dir, "pb")), patch(
        "serve.ansible_runner.run_async", return_value=(thread, runner)
    ), patch("serve.os.listdir", return_value=[]), patch("serve.shutil.rmtree"), patch(
        "serve.time.sleep"
    ):
        serve.run_ansible_background(
            job_id,
            {
                "hosts": "10.0.0.5",
                "playbook": "pb",
                "vault_password": "pw",
                "become_file": "creds",
            },
        )


def _stats(failures=None, dark=None):
    return _event(
        "PLAY RECAP",
        "playbook_on_stats",
        ok={"10.0.0.5": 3},
        changed={"10.0.0.5": 1},
        failures=failures or {},
        dark=dark or {},
    )


def test_endpoint_records_queued_run_and_links_request(db, fake_redis):
    runs, requests = db
    requests.insert_one({"request_id": "req-1", "job_ids": []})

    with patch("serve.Process") as process:
        resp, status = unwrap(serve.run_ansible_endpoint)(
            json.dumps(
                {
                    "hosts": "10.0.0.5, 10.0.0.6",
                    "playbook": "pb",
                    "vault_password": "secret",
                    "become_file": "creds",
                    "request_id": "req-1",
                }
            )
        )
    assert status == 200
    process.return_value.start.assert_called_once()

    run = runs.find_one({"job_id": resp["job_id"]})
    assert run["status"] == "queued"
    assert run["hosts"] == ["10.0.0.5", "10.0.0.6"]
    assert run["request_id"] == "req-1"
    assert "secret" not in json.dumps(run, default=str)
    assert requests.find_one({"request_id": "req-1"})["job_ids"] == [resp["job_id"]]


def test_background_success_records_stats_and_logs(db, fake_redis):
    runs, _ = db
    runs.insert_one({"job_id": "job-ok", "status": "queued"})

    _run(
        "job-ok",
        [
            _event("TASK [ping]"),
            _event("ok: [10.0.0.5]", "runner_on_ok", host="10.0.0.5"),
            _stats(),
        ],
    )

    run = runs.find_one({"job_id": "job-ok"})
    assert run["status"] == "completed"
    assert run["outcome"] == "success"
    assert run["stats"]["ok"] == {"10.0.0.5": 3}
    assert run["failures"] == []
    assert run["logs"] == ["TASK [ping]", "ok: [10.0.0.5]", "PLAY RECAP"]
    assert run["logs_truncated"] is False
    assert run["started_at"] and run["finished_at"]
    # Live Redis log still streamed for the Deploy page
    assert fake_redis.hget("job-ok", "status") == b"completed"


def test_background_failed_tasks_marked_failed(db, fake_redis):
    runs, _ = db
    runs.insert_one({"job_id": "job-fail", "status": "queued"})

    _run(
        "job-fail",
        [
            _event(
                "ignored",
                "runner_on_failed",
                host="10.0.0.5",
                task="optional",
                ignore_errors=True,
                res={"msg": "meh"},
            ),
            _event(
                "fatal",
                "runner_on_failed",
                host="10.0.0.5",
                task="install nginx",
                res={"msg": "No package matching 'nginx'"},
            ),
            _event(
                "unreachable",
                "runner_on_unreachable",
                host="10.0.0.6",
                task="Gathering Facts",
                res={"msg": "ssh timeout"},
            ),
            _stats(failures={"10.0.0.5": 1}, dark={"10.0.0.6": 1}),
        ],
    )

    run = runs.find_one({"job_id": "job-fail"})
    assert run["status"] == "completed"
    assert run["outcome"] == "failed"
    assert [(f["host"], f["task"], f["msg"]) for f in run["failures"]] == [
        ("10.0.0.5", "install nginx", "No package matching 'nginx'"),
        ("10.0.0.6", "Gathering Facts", "ssh timeout"),
    ]


def test_background_without_recap_is_failed(db, fake_redis):
    """A play that dies before the recap (e.g. bad vault password) is not a success."""
    runs, _ = db
    runs.insert_one({"job_id": "job-norecap", "status": "queued"})
    _run("job-norecap", [_event("ERROR! Decryption failed")])
    run = runs.find_one({"job_id": "job-norecap"})
    assert run["outcome"] == "failed"
    assert run["stats"] is None


def test_background_setup_error_recorded(db, fake_redis):
    """A missing playbook/become file must not leave the run stuck at 'queued'."""
    runs, _ = db
    runs.insert_one({"job_id": "job-err", "status": "queued"})
    with patch(
        "serve.ansible_helper.run_ansible", side_effect=Exception("No YML file found.")
    ), patch("serve.shutil.rmtree") as rmtree:
        serve.run_ansible_background(
            "job-err",
            {
                "hosts": "h",
                "playbook": "nope",
                "vault_password": "pw",
                "become_file": "creds",
            },
        )
    rmtree.assert_not_called()

    run = runs.find_one({"job_id": "job-err"})
    assert run["status"] == "error"
    assert run["error"] == "No YML file found."
    assert fake_redis.hget("job-err", "status") == b"error"


def test_background_logs_keep_tail_when_truncated(db, fake_redis, monkeypatch):
    runs, _ = db
    runs.insert_one({"job_id": "job-big", "status": "queued"})
    monkeypatch.setattr(serve, "ANSIBLE_LOG_LIMIT", 25)
    _run("job-big", [_event("x" * 20), _event("y" * 10), _stats()])

    run = runs.find_one({"job_id": "job-big"})
    assert run["logs"] == ["y" * 10, "PLAY RECAP"]
    assert run["logs_truncated"] is True


def test_list_and_get_runs(db, fake_redis):
    runs, _ = db
    runs.insert_many(
        [
            {
                "job_id": "old",
                "status": "completed",
                "created_at": "2026-01-01T00:00:00+00:00",
                "logs": ["done"],
            },
            {
                "job_id": "new",
                "status": "running",
                "created_at": "2026-02-01T00:00:00+00:00",
                "logs": [],
            },
        ]
    )
    fake_redis.rpush("new_log", "TASK [live]")

    listed = json.loads(unwrap(serve.list_ansible_runs)()[0])
    assert [x["job_id"] for x in listed] == ["new", "old"]
    assert all("logs" not in x for x in listed)
    assert len(json.loads(unwrap(serve.list_ansible_runs)(1)[0])) == 1

    assert json.loads(unwrap(serve.get_ansible_run)("old")[0])["logs"] == ["done"]
    assert json.loads(unwrap(serve.get_ansible_run)("new")[0])["logs"] == [
        "TASK [live]"
    ]
    assert unwrap(serve.get_ansible_run)("missing")[1] == 404


def _request(**overrides):
    base = {
        "hosts": ["10.0.0.5"],
        "playbook": "existing",
        "become_file": "creds.yml",
    }
    base.update(overrides)
    return json.dumps(base)


def test_create_request_for_existing_playbook(db, uploads):
    _, requests = db
    resp, status = unwrap(serve.create_ansible_request)(
        _request(hosts="10.0.0.5,10.0.0.6", notes="patch nginx")
    )
    assert status == 200
    assert resp["path"] == "/deploy?request={}".format(resp["request_id"])

    found = requests.find_one({"request_id": resp["request_id"]})
    assert found["hosts"] == ["10.0.0.5", "10.0.0.6"]
    assert found["become_file"] == "creds"
    assert found["playbook_content"] == ""
    assert found["overwrites_playbook"] is False


def test_create_request_with_generated_playbook(db, uploads):
    _, requests = db
    content = "- hosts: all\n  tasks:\n    - ping:\n"

    resp, status = unwrap(serve.create_ansible_request)(
        _request(playbook="ai_new.yml", playbook_content=content)
    )
    assert status == 200
    found = requests.find_one({"request_id": resp["request_id"]})
    assert found["playbook"] == "ai_new"
    assert found["playbook_content"] == content
    assert found["overwrites_playbook"] is False

    resp, _ = unwrap(serve.create_ansible_request)(_request(playbook_content=content))
    found = requests.find_one({"request_id": resp["request_id"]})
    assert found["overwrites_playbook"] is True


@pytest.mark.parametrize(
    "overrides,code",
    [
        ({"hosts": []}, 482),
        ({"playbook": ""}, 482),
        ({"become_file": "nope"}, 483),
        ({"playbook": "missing"}, 484),
        ({"playbook": "new", "playbook_content": "a: [unclosed"}, 471),
    ],
)
def test_create_request_rejects_bad_input(db, uploads, overrides, code):
    _, requests = db
    assert unwrap(serve.create_ansible_request)(_request(**overrides))[1] == code
    assert requests.count_documents({}) == 0


def test_get_request_includes_runs(db, uploads):
    runs, _ = db
    resp, _ = unwrap(serve.create_ansible_request)(_request())
    request_id = resp["request_id"]
    runs.insert_one(
        {
            "job_id": "j1",
            "request_id": request_id,
            "status": "completed",
            "outcome": "success",
            "created_at": "2026-01-01T00:00:00+00:00",
            "logs": ["noise"],
        }
    )
    runs.insert_one({"job_id": "other", "request_id": "elsewhere"})

    found = json.loads(unwrap(serve.get_ansible_request)(request_id)[0])
    assert found["playbook"] == "existing"
    assert [r["job_id"] for r in found["runs"]] == ["j1"]
    assert "logs" not in found["runs"][0]

    assert unwrap(serve.get_ansible_request)("missing")[1] == 404
