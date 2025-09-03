import json
import uuid
from unittest.mock import MagicMock, patch
import pytest

# Import the endpoint functions directly
from serve import run_ansible_endpoint, get_ansible_status
from common.test import unwrap


class FakeRedis:
    """A minimal Redis drop-in used by endpoint/status tests."""

    def __init__(self):
        self.h = {}
        self.l = {}

    # Hash ops
    def hset(self, name, key, value):
        name = name.encode() if isinstance(name, str) else name
        key = key.encode() if isinstance(key, str) else key
        value = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        self.h.setdefault(name, {})
        self.h[name][key] = value

    def hget(self, name, key):
        name = name.encode() if isinstance(name, str) else name
        key = key.encode() if isinstance(key, str) else key
        if name in self.h and key in self.h[name]:
            return self.h[name][key]
        return None

    # List ops
    def rpush(self, name, value):
        name = name.encode() if isinstance(name, str) else name
        value = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        self.l.setdefault(name, [])
        self.l[name].append(value)

    def lrange(self, name, start, end):
        name = name.encode() if isinstance(name, str) else name
        if name not in self.l:
            return []
        # simple slice handling; Redis end is inclusive, Python slice is exclusive
        seq = self.l[name]
        if end == -1:
            return seq[start:]
        return seq[start : end + 1]


def _sample_payload(**overrides):
    base = {
        "hosts": "localhost",
        "playbook": "sample_playbook",
        "vault_password": "password",
        "become_file": "become_file_path",
    }
    base.update(overrides)
    return json.dumps(base)


@patch("serve.redis.Redis")
@patch("serve.Process")
def test_run_ansible_endpoint_starts_background_process(mock_process, mock_redis):
    fake = FakeRedis()
    mock_redis.return_value = fake

    # Mock Process so we don't actually start a child process
    proc = MagicMock()
    mock_process.return_value = proc

    resp, code = unwrap(run_ansible_endpoint)(inp_data=_sample_payload())

    assert code == 200
    assert isinstance(resp, dict)
    assert resp["status"] == "started"
    assert resp["job_id"].startswith("ansible_job_")

    # Ensure process was created with correct target and args and started
    assert (
        mock_process.call_args.kwargs.get("target").__name__ == "run_ansible_background"
    )
    args = mock_process.call_args.kwargs.get("args")
    assert len(args) == 2  # (job_id, data)
    assert args[0] == resp["job_id"]
    assert isinstance(args[1], dict)
    proc.start.assert_called_once()

    # The job should be queued in Redis
    assert fake.hget(resp["job_id"], "status") == b"queued"


def test_run_ansible_endpoint_missing_required_field_returns_482():
    # missing vault_password
    bad_payload = json.dumps(
        {
            "hosts": "localhost",
            "playbook": "sample_playbook",
            "become_file": "become_file_path",
        }
    )

    resp, code = unwrap(run_ansible_endpoint)(inp_data=bad_payload)
    assert resp == "Invalid data"
    assert code == 482


@patch("serve.redis.Redis")
def test_get_ansible_status_returns_logs_and_results(mock_redis):
    fake = FakeRedis()
    mock_redis.return_value = fake

    job_id = f"ansible_job_{uuid.uuid4()}"
    # Seed Redis state as if background worker had run
    fake.hset(job_id, "status", "completed")
    fake.rpush(f"{job_id}_log", "log line 1")
    fake.rpush(f"{job_id}_log", "log line 2")
    fake.hset(job_id, "results", json.dumps(["ok line", "changed line"]))

    resp, code = unwrap(get_ansible_status)(job_id)
    assert code == 200
    # assert resp["job_id"] == job_id
    assert resp["status"] == "completed"
    assert resp["logs"] == ["log line 1", "log line 2"]
    assert resp["results"] == ["ok line", "changed line"]


@patch("serve.redis.Redis")
def test_get_ansible_status_unknown_job_returns_404(mock_redis):
    fake = FakeRedis()
    mock_redis.return_value = fake

    resp, code = unwrap(get_ansible_status)("ansible_job_missing")
    assert code == 404
    assert resp == {"error": "Job not found"}
