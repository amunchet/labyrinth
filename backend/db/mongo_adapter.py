"""
MongoDB adapter: a thin, near-zero-risk passthrough onto real pymongo.

This is the fallback backend (`DB_BACKEND=mongo`). It exists so an existing
Mongo deployment can keep running unchanged while Postgres/TimescaleDB is
the new default - see MONGO_MIGRATION.md. Because it forwards raw filter/
update dicts straight to pymongo, it supports the *full* MongoDB query
language, not just the narrow subset `postgres_adapter.py` translates.
"""

import os

import pymongo

from db import base


def _build_uri():
    username = os.environ.get("MONGO_USERNAME")
    password = os.environ.get("MONGO_PASSWORD")
    host = os.environ.get("MONGO_HOST")
    if os.getenv("GITHUB") or os.getenv("TESTBED"):
        return "mongodb://{}:{}@{}".format(username, password, host)
    return "mongodb+srv://{}:{}@{}".format(username, password, host)  # pragma: no cover


def _to_real_op(op):
    if isinstance(op, base.InsertOne):
        return pymongo.InsertOne(op.document)
    if isinstance(op, base.ReplaceOne):
        return pymongo.ReplaceOne(op.filter, op.replacement, upsert=op.upsert)
    if isinstance(op, base.UpdateOne):
        return pymongo.UpdateOne(op.filter, op.update, upsert=op.upsert)
    if isinstance(op, base.DeleteOne):
        return pymongo.DeleteOne(op.filter)
    raise TypeError(f"Unsupported bulk op: {type(op).__name__}")


class MongoCursorAdapter(base.Cursor):
    def __init__(self, cursor):
        self._cursor = cursor

    def sort(self, key_or_list, direction=None):
        if direction is None:
            self._cursor = self._cursor.sort(key_or_list)
        else:
            self._cursor = self._cursor.sort(key_or_list, direction)
        return self

    def limit(self, n):
        self._cursor = self._cursor.limit(n)
        return self

    def __iter__(self):
        return iter(self._cursor)


class MongoCollectionAdapter(base.Collection):
    def __init__(self, coll):
        self._coll = coll

    def find(self, filter=None, sort=None, limit=None):
        cursor = MongoCursorAdapter(self._coll.find(filter or {}))
        if sort is not None:
            cursor.sort(sort)
        if limit is not None:
            cursor.limit(limit)
        return cursor

    def find_one(self, filter=None):
        return self._coll.find_one(filter or {})

    def insert_one(self, document):
        result = self._coll.insert_one(document)
        return base.InsertOneResult(result.inserted_id)

    def insert_many(self, documents):
        result = self._coll.insert_many(documents)
        return base.InsertManyResult(result.inserted_ids)

    def update_one(self, filter, update, upsert=False):
        result = self._coll.update_one(filter, update, upsert=upsert)
        return base.UpdateResult(
            result.matched_count, result.modified_count, result.upserted_id
        )

    def update_many(self, filter, update, upsert=False):
        result = self._coll.update_many(filter, update, upsert=upsert)
        return base.UpdateResult(
            result.matched_count, result.modified_count, result.upserted_id
        )

    def delete_one(self, filter):
        result = self._coll.delete_one(filter)
        return base.DeleteResult(result.deleted_count)

    def delete_many(self, filter):
        result = self._coll.delete_many(filter)
        return base.DeleteResult(result.deleted_count)

    def bulk_write(self, operations):
        real_ops = [_to_real_op(op) for op in operations]
        result = self._coll.bulk_write(real_ops)
        return base.BulkWriteResult(
            inserted_count=result.inserted_count,
            matched_count=result.matched_count,
            modified_count=result.modified_count,
            deleted_count=result.deleted_count,
            upserted_count=result.upserted_count,
        )

    def count_documents(self, filter=None):
        return self._coll.count_documents(filter or {})

    def create_index(self, keys, **kwargs):
        return self._coll.create_index(keys, **kwargs)

    def drop_index(self, name_or_keys):
        return self._coll.drop_index(name_or_keys)


class MongoDatabaseAdapter(base.Database):
    def __init__(self, db):
        self._db = db

    def __getitem__(self, collection_name):
        return MongoCollectionAdapter(self._db[collection_name])


class MongoClientAdapter(base.Client):
    def __init__(self):
        self._client = pymongo.MongoClient(_build_uri())

    def __getitem__(self, database_name):
        return MongoDatabaseAdapter(self._client[database_name])

    def close(self):
        self._client.close()
