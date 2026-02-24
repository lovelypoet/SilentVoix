"""
MongoDB implementation of :class:`~db.repository.AbstractRepository`.

Wraps a :class:`motor.motor_asyncio.AsyncIOMotorCollection` and delegates
every operation to the Motor async driver.  Swap this class for a different
:class:`~db.repository.AbstractRepository` subclass to migrate to another
database backend without changing any route or service code.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

from motor.motor_asyncio import AsyncIOMotorCollection

from db.repository import (
    AbstractRepository,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)


class MongoRepository(AbstractRepository):
    """MongoDB-backed repository that wraps a Motor collection.

    Parameters
    ----------
    collection:
        An :class:`motor.motor_asyncio.AsyncIOMotorCollection` instance
        obtained from the shared Motor client in ``core.database``.
    """

    def __init__(self, collection: AsyncIOMotorCollection) -> None:
        self._col = collection

    # --- Queries -----------------------------------------------------------

    async def find_one(
        self,
        filter: Dict[str, Any],
        sort: Optional[List[Tuple[str, int]]] = None,
    ) -> Optional[Dict[str, Any]]:
        kwargs: Dict[str, Any] = {}
        if sort:
            kwargs["sort"] = sort
        return await self._col.find_one(filter, **kwargs)

    def find(
        self,
        filter: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        projection: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        cursor = self._col.find(filter or {}, projection)
        if sort:
            cursor = cursor.sort(sort)
        return cursor

    async def count_documents(
        self,
        filter: Optional[Dict[str, Any]] = None,
    ) -> int:
        return await self._col.count_documents(filter or {})

    # --- Mutations ---------------------------------------------------------

    async def insert_one(
        self,
        document: Dict[str, Any],
    ) -> InsertOneResult:
        result = await self._col.insert_one(document)
        return InsertOneResult(inserted_id=str(result.inserted_id))

    async def insert_many(
        self,
        documents: List[Dict[str, Any]],
    ) -> InsertManyResult:
        result = await self._col.insert_many(documents)
        return InsertManyResult(
            inserted_ids=[str(oid) for oid in result.inserted_ids]
        )

    async def update_one(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
    ) -> UpdateResult:
        result = await self._col.update_one(filter, update)
        return UpdateResult(
            matched_count=result.matched_count,
            modified_count=result.modified_count,
        )

    async def delete_one(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        result = await self._col.delete_one(filter)
        return DeleteResult(deleted_count=result.deleted_count)

    async def delete_many(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        result = await self._col.delete_many(filter)
        return DeleteResult(deleted_count=result.deleted_count)

    # --- Schema / indexes --------------------------------------------------

    async def create_index(
        self,
        keys: Union[str, List[Tuple[str, int]]],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        kwargs: Dict[str, Any] = {"unique": unique}
        if name:
            kwargs["name"] = name
        await self._col.create_index(keys, **kwargs)
