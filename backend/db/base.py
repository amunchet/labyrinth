"""
Database adapter interface.

This defines the pymongo-shaped surface that `backend/serve.py` and friends
are actually written against (cataloged exhaustively against the real
codebase - see MONGO_MIGRATION.md). It is deliberately narrow: only the
methods/operators genuinely used anywhere in this repo are part of the
contract. `mongo_adapter.py` and `postgres_adapter.py` both implement this
interface; callers program against `Client`/`Database`/`Collection`/`Cursor`
only, never against a concrete backend.
"""

from abc import ABC, abstractmethod

# --- Bulk-op value objects (structural stand-ins for pymongo's) -----------


class InsertOne:
    def __init__(self, document):
        self.document = document


class ReplaceOne:
    def __init__(self, filter, replacement, upsert=False):
        self.filter = filter
        self.replacement = replacement
        self.upsert = upsert


class UpdateOne:
    def __init__(self, filter, update, upsert=False):
        self.filter = filter
        self.update = update
        self.upsert = upsert


class DeleteOne:
    def __init__(self, filter):
        self.filter = filter


# --- Result value objects ---------------------------------------------------


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class UpdateResult:
    def __init__(self, matched_count, modified_count, upserted_id=None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class BulkWriteResult:
    def __init__(
        self,
        inserted_count=0,
        matched_count=0,
        modified_count=0,
        deleted_count=0,
        upserted_count=0,
    ):
        self.inserted_count = inserted_count
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.deleted_count = deleted_count
        self.upserted_count = upserted_count


# --- Cursor / Collection / Database / Client interfaces --------------------


class Cursor(ABC):
    """Lazy, chainable result set - mirrors the pymongo.Cursor subset used
    in this codebase (`.sort()` in both list-of-tuples and key+direction
    form, `.limit()`, plain iteration)."""

    @abstractmethod
    def sort(self, key_or_list, direction=None): ...

    @abstractmethod
    def limit(self, n): ...

    @abstractmethod
    def __iter__(self): ...


class Collection(ABC):
    @abstractmethod
    def find(self, filter=None, sort=None, limit=None): ...

    @abstractmethod
    def find_one(self, filter=None): ...

    @abstractmethod
    def insert_one(self, document): ...

    @abstractmethod
    def insert_many(self, documents): ...

    @abstractmethod
    def update_one(self, filter, update, upsert=False): ...

    @abstractmethod
    def update_many(self, filter, update, upsert=False): ...

    @abstractmethod
    def delete_one(self, filter): ...

    @abstractmethod
    def delete_many(self, filter): ...

    @abstractmethod
    def bulk_write(self, operations): ...

    @abstractmethod
    def count_documents(self, filter=None): ...

    @abstractmethod
    def create_index(self, keys, **kwargs): ...

    @abstractmethod
    def drop_index(self, name_or_keys): ...


class Database(ABC):
    @abstractmethod
    def __getitem__(self, collection_name): ...


class Client(ABC):
    @abstractmethod
    def __getitem__(self, database_name): ...

    @abstractmethod
    def close(self): ...
