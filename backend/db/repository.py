"""
Abstract database repository interface for the sign glove system.

Defines the contract that any database backend must implement, enabling
migration from MongoDB to other databases (e.g. PostgreSQL) without
changing route or service code.

Usage
-----
Import the abstract class and result types when writing new repository
implementations or type-hinting dependencies::

    from db.repository import AbstractRepository, InsertOneResult

To use the MongoDB implementation that ships with the application, import
from ``core.database``::

    from core.database import sensor_repo          # MongoRepository instance
    # or for full type-checking:
    from db.repository import AbstractRepository
    from core.database import sensor_repo as repo  # AbstractRepository
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# Database-agnostic result types
# ---------------------------------------------------------------------------

@dataclass
class InsertOneResult:
    """Result returned by :meth:`AbstractRepository.insert_one`."""

    inserted_id: str


@dataclass
class InsertManyResult:
    """Result returned by :meth:`AbstractRepository.insert_many`."""

    inserted_ids: List[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    """Result returned by :meth:`AbstractRepository.update_one`."""

    matched_count: int
    modified_count: int


@dataclass
class DeleteResult:
    """Result returned by :meth:`AbstractRepository.delete_one` and
    :meth:`AbstractRepository.delete_many`."""

    deleted_count: int


# ---------------------------------------------------------------------------
# Abstract repository
# ---------------------------------------------------------------------------

class AbstractRepository(ABC):
    """Abstract base class defining the database repository interface.

    All concrete implementations (MongoDB, PostgreSQL, in-memory for tests,
    etc.) must implement every method listed here, enabling drop-in
    replacement without touching route or service code.

    Query filters follow the MongoDB operator convention (``$set``, ``$lt``,
    etc.) as the primary dialect; alternative backends are expected to
    translate these to their native semantics in their own implementation.

    Sort lists use ``(field, direction)`` tuples where direction is
    ``1`` (ascending) or ``-1`` (descending), again mirroring the MongoDB
    convention for familiarity.
    """

    # --- Queries -----------------------------------------------------------

    @abstractmethod
    async def find_one(
        self,
        filter: Dict[str, Any],
        sort: Optional[List[Tuple[str, int]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return the first document matching *filter*, or ``None``.

        Parameters
        ----------
        filter:
            Field/value pairs (and operators) that the document must match.
        sort:
            Optional list of ``(field, direction)`` tuples used to order
            candidates before selecting the first one.
        """

    @abstractmethod
    def find(
        self,
        filter: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        projection: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Return an async iterator over documents matching *filter*.

        Parameters
        ----------
        filter:
            Field/value pairs that documents must match.  ``None`` or ``{}``
            matches every document in the collection.
        sort:
            Optional list of ``(field, direction)`` tuples.
        projection:
            Optional mapping specifying which fields to include (``1``) or
            exclude (``0``).

        Usage::

            async for doc in repo.find({"label": "hello"}, sort=[("timestamp", -1)]):
                process(doc)
        """

    @abstractmethod
    async def count_documents(
        self,
        filter: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Return the number of documents matching *filter*."""

    # --- Mutations ---------------------------------------------------------

    @abstractmethod
    async def insert_one(
        self,
        document: Dict[str, Any],
    ) -> InsertOneResult:
        """Insert *document* and return an :class:`InsertOneResult`."""

    @abstractmethod
    async def insert_many(
        self,
        documents: List[Dict[str, Any]],
    ) -> InsertManyResult:
        """Insert *documents* and return an :class:`InsertManyResult`."""

    @abstractmethod
    async def update_one(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
    ) -> UpdateResult:
        """Update the first document matching *filter* using *update*.

        The *update* value uses MongoDB operator syntax (e.g. ``{"$set":
        {"field": value}}``).  Other backends should translate these
        operators to their native update semantics.
        """

    @abstractmethod
    async def delete_one(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        """Delete the first document matching *filter*."""

    @abstractmethod
    async def delete_many(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        """Delete all documents matching *filter*."""

    # --- Schema / indexes --------------------------------------------------

    @abstractmethod
    async def create_index(
        self,
        keys: Union[str, List[Tuple[str, int]]],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """Ensure an index exists for *keys*.

        Parameters
        ----------
        keys:
            A single field name (``str``) for a simple index, or a list of
            ``(field, direction)`` tuples for a compound index.
        unique:
            When ``True``, enforce uniqueness across the indexed field(s).
        name:
            Optional explicit index name; useful for referencing the index
            later (e.g. to drop it).
        """
