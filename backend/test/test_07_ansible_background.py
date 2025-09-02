import json
import time
from unittest.mock import MagicMock, patch
import pytest

from common.test import unwrap
from serve import run_ansible_background


class FakeRedis:
    def __init__(self):
        self.h = {}
        self.l = {}

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

    def rpush(self, name, value):
        name = name.encode() if isinstance(name, str) else name
        value = value if isinstance(value, (bytes, bytearray)) else str(value).encode()
        self.l.setdefault(name, [])
        self.l[name].append(value)

    def lrange(self, name, start, end):
        name = name.encode() if isinstance(name, str) else name
        if name not in self.l:
            return []
        seq = self.l[name]
        if end == -1:
            return seq[start:]
        return seq[start : end + 1]


def _input_data(**overrides):
    base = {
        "hosts": "localhost",
        "playbook": "sample_playbook",
        "vault_password": "password",
        "become_file": "become_file_path",
        # ssh_key optional
    }
    base.update(overrides)
    return base


@patch("serve.shutil.rmtree")
@patch("serve.os.remove")
@patch("serve.os.path.exists")
@patch("serve.os.listdir")
@patch("serve.ansible_runner.run_async")
@patch("serve.ansible_helper.run_ansible")
@patch("serve.redis.Redis")
@patch("serve.time.sleep", lambda *args, **kwargs: None)  # speed up loop
def test_run_ansible_background_streams_events_and_completes(
    mock_redis,
    mock_run_ansible,
    mock_run_async,
    mock_listdir,
    mock_exists,
    mock_remove,
    mock_rmtree,
):
    # Fake redis instance
    fake = FakeRedis()
    mock_redis.return_value = fake

    # ansible_helper.run_ansible returns RUN_DIR and playbook name
    mock_run_ansible.return_value = ("/tmp/RUN_DIR_123", "my_playbook")

    # Simulate runner/thread behavior
    mock_thread = MagicMock()
    mock_thread.is_alive.side_effect = [True, False]  # one loop pass
    mock_runner = MagicMock()
    mock_runner.events = [
        {
            "stdout": "TASK [ping] *********************************************************"
        },
        {"stdout": "ok: [localhost]"},
    ]
    mock_run_async.return_value = (mock_thread, mock_runner)

    # Ensure vault cleanup branch executes
    mock_listdir.return_value = ["vault.pass"]
    mock_exists.return_value = False  # /vault.pass does not exist

    job_id = "ansible_job_test"
    data = _input_data()

    run_ansible_background(job_id, data)

    # Status transitions
    assert fake.hget(job_id, "status") == b"completed"
    logs = fake.lrange(f"{job_id}_log", 0, -1)
    assert b"TASK [ping]" in logs[0]
    assert b"ok: [localhost]" in logs[1]

    # Results list stored
    results = json.loads(fake.hget(job_id, "results").decode())
    assert "TASK [ping]" in results[0]
    assert "ok: [localhost]" in results[1]

    # Called to remove vault and cleanup dir
    mock_remove.assert_called_once_with("/tmp/RUN_DIR_123/vault.pass")
    mock_rmtree.assert_called_once_with("/tmp/RUN_DIR_123")


@patch("serve.shutil.rmtree")
@patch("serve.os.remove")
@patch("serve.os.path.exists")
@patch("serve.os.listdir")
@patch("serve.ansible_runner.run_async")
@patch("serve.ansible_helper.run_ansible")
@patch("serve.redis.Redis")
@patch("serve.time.sleep", lambda *args, **kwargs: None)
def test_run_ansible_background_sets_error_on_exception(
    mock_redis,
    mock_run_ansible,
    mock_run_async,
    mock_listdir,
    mock_exists,
    mock_remove,
    mock_rmtree,
):
    fake = FakeRedis()
    mock_redis.return_value = fake

    mock_run_ansible.return_value = ("/tmp/RUN_DIR_ERR", "err_playbook")

    # Make run_async raise
    mock_run_async.side_effect = RuntimeError("boom")

    # Cleanups
    mock_listdir.return_value = ["vault.pass"]
    mock_exists.return_value = True

    job_id = "ansible_job_err"
    data = _input_data()

    run_ansible_background(job_id, data)

    assert fake.hget(job_id, "status") == b"error"
    assert fake.hget(job_id, "error") == b"boom"

    # Both possible vault locations are attempted by code-path; ensure rmtree called
    mock_rmtree.assert_called_once_with("/tmp/RUN_DIR_ERR")
