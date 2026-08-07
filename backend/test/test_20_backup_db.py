#!/usr/bin/env python3
"""
Tests for backend/backup_db.py. Mocks the subprocess boundary (pg_dump/
pg_restore) rather than requiring postgresql-client tooling inside the
backend test image - the cron image that actually runs this script in
production does have it installed (cron/Dockerfile). This mirrors how other
external-process interactions in this repo (e.g. ansible_runner) are tested.
"""

import os
import pathlib
import shutil
import subprocess

import pytest

import backup_db

# A directory under the checked-out source tree, not pytest's tmp_path -
# some unrelated, pre-existing test elsewhere in the suite can delete /tmp
# mid-run (see MONGO_MIGRATION.md), which would otherwise take tmp_path (and
# every test using it) down too.
_SCRATCH_DIR = pathlib.Path(__file__).resolve().parent / ".backup_test_scratch"


@pytest.fixture
def backup_dir(monkeypatch):
    if _SCRATCH_DIR.exists():
        shutil.rmtree(_SCRATCH_DIR)
    _SCRATCH_DIR.mkdir()
    monkeypatch.setattr(backup_db, "BACKUP_DIR", str(_SCRATCH_DIR))
    yield _SCRATCH_DIR
    shutil.rmtree(_SCRATCH_DIR, ignore_errors=True)


def test_skips_when_not_postgres_backend(monkeypatch, backup_dir):
    monkeypatch.setenv("DB_BACKEND", "mongo")
    assert backup_db.backup_db() == 0
    assert list(backup_dir.iterdir()) == []


def test_successful_backup(monkeypatch, backup_dir, capsys):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("POSTGRES_DB", "labyrinth")

    def fake_run(cmd, env=None, check=None, capture_output=None, text=None):
        if cmd[0] == "pg_dump":
            # Simulate pg_dump actually writing the dump file.
            dump_path = cmd[cmd.index("--file") + 1]
            with open(dump_path, "wb") as f:
                f.write(b"fake dump contents")
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[0] == "pg_restore":
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError("unexpected command: {}".format(cmd))

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backup_db.backup_db()
    assert result == 0

    files = list(backup_dir.iterdir())
    assert len(files) == 1
    assert files[0].name.startswith("labyrinth-labyrinth-")
    assert files[0].name.endswith(".dump")

    out = capsys.readouterr().out
    assert "BACKUP OK:" in out


def test_pg_dump_failure_reports_failed(monkeypatch, backup_dir, capsys):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    def fake_run(cmd, env=None, check=None, capture_output=None, text=None):
        raise subprocess.CalledProcessError(1, cmd, stderr="connection refused")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backup_db.backup_db()
    assert result == 1
    assert "BACKUP FAILED:" in capsys.readouterr().out


def test_empty_dump_file_reports_failed(monkeypatch, backup_dir, capsys):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    def fake_run(cmd, env=None, check=None, capture_output=None, text=None):
        if cmd[0] == "pg_dump":
            dump_path = cmd[cmd.index("--file") + 1]
            open(dump_path, "wb").close()  # zero-byte file
            return subprocess.CompletedProcess(cmd, 0)
        raise AssertionError("pg_restore should not be reached")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backup_db.backup_db()
    assert result == 1
    assert "BACKUP FAILED:" in capsys.readouterr().out


def test_pg_restore_sanity_check_failure_reports_failed(
    monkeypatch, backup_dir, capsys
):
    monkeypatch.setenv("DB_BACKEND", "postgres")

    def fake_run(cmd, env=None, check=None, capture_output=None, text=None):
        if cmd[0] == "pg_dump":
            dump_path = cmd[cmd.index("--file") + 1]
            with open(dump_path, "wb") as f:
                f.write(b"not actually a valid dump")
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[0] == "pg_restore":
            raise subprocess.CalledProcessError(1, cmd, stderr="corrupt dump file")
        raise AssertionError("unexpected command: {}".format(cmd))

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = backup_db.backup_db()
    assert result == 1
    assert "BACKUP FAILED:" in capsys.readouterr().out


def test_local_retention_prunes_old_backups(monkeypatch, backup_dir):
    monkeypatch.setenv("DB_BACKEND", "postgres")
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "1")

    old_file = backup_dir / "labyrinth-labyrinth-20200101T000000Z.dump"
    old_file.write_bytes(b"old")
    old_time = (
        __import__("datetime").datetime.now() - __import__("datetime").timedelta(days=5)
    ).timestamp()
    os.utime(old_file, (old_time, old_time))

    def fake_run(cmd, env=None, check=None, capture_output=None, text=None):
        if cmd[0] == "pg_dump":
            dump_path = cmd[cmd.index("--file") + 1]
            with open(dump_path, "wb") as f:
                f.write(b"fake dump contents")
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    backup_db.backup_db()

    remaining = {p.name for p in backup_dir.iterdir()}
    assert old_file.name not in remaining
