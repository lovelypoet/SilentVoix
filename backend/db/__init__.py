"""
Database abstraction layer for the sign glove system.

Exports:
- :class:`AbstractRepository` – interface every backend must implement
- :class:`MongoRepository`    – Motor/MongoDB implementation
- Result types: :class:`InsertOneResult`, :class:`InsertManyResult`,
  :class:`UpdateResult`, :class:`DeleteResult`
"""
from db.repository import (
    AbstractRepository,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)
from db.mongo_repository import MongoRepository

__all__ = [
    "AbstractRepository",
    "MongoRepository",
    "InsertOneResult",
    "InsertManyResult",
    "UpdateResult",
    "DeleteResult",
]
