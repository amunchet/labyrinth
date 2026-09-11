#!/usr/bin/env python3
"""
Tests for the persist=False validate-without-writing behavior of check_file,
and the new synchronous run_adhoc() ad-hoc command runner used by diagnostic
tools in the AI chat feature.
"""
import os
import shutil
from unittest.mock import MagicMock, patch

import pytest

from ansible_helper import check_file, run_adhoc


@pytest.fixture
def setup_become():  # pragma: no cover
    if not os.path.exists("/src/uploads/become"):
        os.makedirs("/src/uploads/become")
    if not os.path.exists("/src/uploads/become/vault.yml"):
        shutil.copy("/src/test/ansible/vars/vault.yml", "/src/uploads/become/vault.yml")


def _startup_yaml():
    with open("/src/test/ansible/project/startup.yml") as f:
        return f.read()


def test_check_file_persist_false_validates_without_writing():
    fname = "chat_draft_test"
    dest = "/src/uploads/ansible/{}.yml".format(fname)
    if os.path.exists(dest):
        os.remove(dest)

    result = check_file(fname, "ansible", raw=_startup_yaml(), persist=False)

    assert result[0] is True
    assert not os.path.exists(dest)


def test_check_file_persist_false_invalid_yaml_no_leftover():
    fname = "chat_draft_invalid"
    dest = "/src/uploads/ansible/{}.yml".format(fname)
    if os.path.exists(dest):
        os.remove(dest)

    result = check_file(fname, "ansible", raw="not: [a, valid, playbook", persist=False)

    assert result[0] is False
    assert not os.path.exists(dest)


def test_check_file_default_persist_still_writes():
    fname = "chat_draft_test_persist_default"
    dest = "/src/uploads/ansible/{}.yml".format(fname)
    if os.path.exists(dest):
        os.remove(dest)

    result = check_file(fname, "ansible", raw=_startup_yaml())

    assert result[0] is True
    assert os.path.exists(dest)
    os.remove(dest)


@patch("ansible_helper.ansible_runner.run")
def test_run_adhoc_executes_command_module(mock_run, setup_become):
    mock_result = MagicMock()
    mock_result.status = "successful"
    mock_result.rc = 0
    mock_result.events = [{"stdout": "Filesystem  Size  Used"}, {"stdout": ""}]
    mock_run.return_value = mock_result

    result = run_adhoc(
        hosts="sampleclient",
        argv=["df", "-h"],
        vault_password="test",
        become_file="vault",
    )

    assert result == {
        "status": "successful",
        "rc": 0,
        "stdout": "Filesystem  Size  Used",
    }

    called_kwargs = mock_run.call_args.kwargs
    assert called_kwargs["module"] == "command"
    assert called_kwargs["module_args"] == "df -h"
    assert called_kwargs["host_pattern"] == "clients"

    # RUN_DIR is cleaned up after the call
    assert not os.path.exists(called_kwargs["private_data_dir"])


@patch("ansible_helper.ansible_runner.run")
def test_run_adhoc_cleans_up_on_exception(mock_run, setup_become):
    mock_run.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        run_adhoc(
            hosts="sampleclient",
            argv=["df", "-h"],
            vault_password="test",
            become_file="vault",
        )

    called_kwargs = mock_run.call_args.kwargs
    assert not os.path.exists(called_kwargs["private_data_dir"])


def test_run_adhoc_missing_become_file_raises():
    with pytest.raises(Exception):
        run_adhoc(
            hosts="sampleclient",
            argv=["df", "-h"],
            vault_password="test",
            become_file="does-not-exist-become-file",
        )
