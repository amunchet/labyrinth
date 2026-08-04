"""Durable storage for AI chat sessions.

Redis remains the active-turn store. This module stores only conversation and
workflow metadata in the management database. Credentials are intentionally
not part of this document.
"""

import time

from db import get_db


COLLECTION = "ai_chat_sessions"


def _collection(db=None):
    if db is not None:
        return db["labyrinth"][COLLECTION]
    # serve.py already owns the process-wide database client. Reuse it when
    # available so session operations do not create a new Postgres pool.
    try:
        import serve

        return serve.db["labyrinth"][COLLECTION]
    except (ImportError, AttributeError):
        return get_db()["labyrinth"][COLLECTION]


def _without_id(document):
    document = dict(document or {})
    document.pop("_id", None)
    return document


def _safe_summary(document):
    item = _without_id(document)
    item["message_count"] = len(item.get("messages") or [])
    item.pop("messages", None)
    item.pop("draft", None)
    return item


def save(session_id, record, db=None):
    """Create or replace a durable session record."""
    document = _without_id(record)
    collection = _collection(db)
    if collection.find_one({"_id": session_id}):
        collection.update_one({"_id": session_id}, {"$set": document})
    else:
        document["_id"] = session_id
        collection.insert_one(document)
    return document


def get(session_id, db=None):
    document = _collection(db).find_one({"_id": session_id})
    return _without_id(document) if document else None


def update(session_id, fields, db=None):
    fields = dict(fields or {})
    fields["updated_at"] = fields.get("updated_at", time.time())
    _collection(db).update_one({"_id": session_id}, {"$set": fields})


def delete(session_id, db=None):
    _collection(db).delete_one({"_id": session_id})


def list_sessions(db=None):
    documents = []
    for document in _collection(db).find({}):
        item = _safe_summary(document)
        item["session_id"] = document.get("_id")
        documents.append(item)
    documents.sort(key=lambda item: float(item.get("updated_at") or 0), reverse=True)
    return documents
