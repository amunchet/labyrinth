#!/usr/bin/env python3
"""Tests for ai/session_store.py - DB-backed durable chat session metadata."""

import time
from unittest.mock import MagicMock, patch

from ai import session_store


class FakeCollection:
    def __init__(self):
        self._docs = {}

    def find_one(self, query):
        key = query.get("_id")
        return dict(self._docs[key]) if key in self._docs else None

    def insert_one(self, document):
        doc = dict(document)
        self._docs[doc["_id"]] = doc

    def update_one(self, query, update):
        key = query.get("_id")
        if key in self._docs:
            self._docs[key].update(update.get("$set", {}))

    def delete_one(self, query):
        key = query.get("_id")
        self._docs.pop(key, None)

    def find(self, query):
        return list(self._docs.values())


def _make_db(collection):
    labyrinth_ns = MagicMock()
    labyrinth_ns.__getitem__ = MagicMock(return_value=collection)
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=labyrinth_ns)
    return db


# ---------------------------------------------------------------------------
# _collection helper
# ---------------------------------------------------------------------------


def test_collection_uses_provided_db():
    col = FakeCollection()
    db = _make_db(col)
    result = session_store._collection(db=db)
    assert result is col


def test_collection_falls_back_to_get_db_on_import_error():
    col = FakeCollection()
    fake_db = _make_db(col)
    with patch("ai.session_store.get_db", return_value=fake_db):
        with patch.dict("sys.modules", {"serve": None}):
            result = session_store._collection()
    assert result is col


# ---------------------------------------------------------------------------
# _safe_summary
# ---------------------------------------------------------------------------


def test_safe_summary_counts_messages_and_strips_them():
    doc = {
        "_id": "s1",
        "provider": "openai",
        "messages": [{"role": "user"}, {"role": "assistant"}],
        "draft": {"yaml": "---"},
    }
    summary = session_store._safe_summary(doc)
    assert summary["message_count"] == 2
    assert "messages" not in summary
    assert "draft" not in summary
    assert "_id" not in summary
    assert summary["provider"] == "openai"


def test_safe_summary_handles_empty_messages():
    doc = {"_id": "s2", "messages": None}
    summary = session_store._safe_summary(doc)
    assert summary["message_count"] == 0


# ---------------------------------------------------------------------------
# save / get / update / delete
# ---------------------------------------------------------------------------


def test_save_creates_new_document():
    col = FakeCollection()
    db = _make_db(col)
    result = session_store.save("sess-1", {"provider": "openai"}, db=db)
    assert result["provider"] == "openai"
    assert "_id" not in result
    assert col.find_one({"_id": "sess-1"}) is not None


def test_save_updates_existing_document():
    col = FakeCollection()
    db = _make_db(col)
    session_store.save("sess-2", {"provider": "openai"}, db=db)
    session_store.save("sess-2", {"provider": "anthropic"}, db=db)
    assert col.find_one({"_id": "sess-2"})["provider"] == "anthropic"


def test_get_returns_document_without_id():
    col = FakeCollection()
    db = _make_db(col)
    session_store.save("sess-3", {"title": "hello"}, db=db)
    result = session_store.get("sess-3", db=db)
    assert result["title"] == "hello"
    assert "_id" not in result


def test_get_returns_none_for_missing():
    col = FakeCollection()
    db = _make_db(col)
    assert session_store.get("missing", db=db) is None


def test_update_sets_fields_and_updated_at():
    col = FakeCollection()
    db = _make_db(col)
    session_store.save("sess-4", {"title": "old"}, db=db)
    before = time.time()
    session_store.update("sess-4", {"title": "new"}, db=db)
    doc = col.find_one({"_id": "sess-4"})
    assert doc["title"] == "new"
    assert doc.get("updated_at", 0) >= before


def test_update_preserves_explicit_updated_at():
    col = FakeCollection()
    db = _make_db(col)
    session_store.save("sess-5", {"title": "t"}, db=db)
    session_store.update("sess-5", {"updated_at": 12345.0}, db=db)
    assert col.find_one({"_id": "sess-5"})["updated_at"] == 12345.0


def test_delete_removes_document():
    col = FakeCollection()
    db = _make_db(col)
    session_store.save("sess-6", {"title": "bye"}, db=db)
    session_store.delete("sess-6", db=db)
    assert col.find_one({"_id": "sess-6"}) is None


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------


def test_list_sessions_summarises_and_sorts():
    col = FakeCollection()
    db = _make_db(col)
    session_store.save(
        "s-a",
        {"provider": "openai", "updated_at": 100.0, "messages": [{"role": "user"}]},
        db=db,
    )
    session_store.save(
        "s-b",
        {"provider": "anthropic", "updated_at": 200.0, "messages": []},
        db=db,
    )
    results = session_store.list_sessions(db=db)
    ids = [r["session_id"] for r in results]
    # Most-recently-updated first
    assert ids[0] == "s-b"
    assert ids[1] == "s-a"
    assert results[1]["message_count"] == 1
    assert "messages" not in results[0]
