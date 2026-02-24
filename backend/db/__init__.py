"""
Database abstraction layer for the sign glove system.

Exports:
- :class:`AbstractRepository`     – interface every backend must implement
- :class:`MongoRepository`        – Motor/MongoDB implementation (current)
- :class:`SQLAlchemyRepository`   – PostgreSQL migration-path implementation
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

# SQLAlchemyRepository is an optional import; sqlalchemy/asyncpg may not be
# installed in environments that only use MongoDB.
try:
    from db.sqlalchemy_repository import SQLAlchemyRepository
    _sa_available = True
except ImportError:  # pragma: no cover
    _sa_available = False

__all__ = [
    "AbstractRepository",
    "MongoRepository",
    "SQLAlchemyRepository",
    "InsertOneResult",
    "InsertManyResult",
    "UpdateResult",
    "DeleteResult",
]
