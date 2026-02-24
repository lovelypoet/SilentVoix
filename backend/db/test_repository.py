"""
In-memory repository implementation and tests for the repository interface.

:class:`InMemoryRepository` is a lightweight, purely-Python implementation of
:class:`~db.repository.AbstractRepository` that requires no running database.
It is useful for:

* **Unit tests** – inject it anywhere a repository is expected.
* **Local offline development** – run the API without MongoDB.
* **Reference implementation** – demonstrates the minimal surface that any
  new backend (PostgreSQL, SQLite, …) must expose.

Run with::

    pytest backend/db/test_repository.py -v
"""
from __future__ import annotations

import copy
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union
from uuid import uuid4

import pytest

from db.repository import (
    AbstractRepository,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)


# ---------------------------------------------------------------------------
# In-memory repository (reference / test double)
# ---------------------------------------------------------------------------

class InMemoryRepository(AbstractRepository):
    """Purely in-memory implementation of :class:`AbstractRepository`.

    Documents are stored as plain dictionaries in a list.  ``_id`` values are
    auto-generated UUIDs (strings) so callers do not need to set them.

    This class is intentionally simple – it is not meant to be a full MongoDB
    emulator.  Complex query operators (beyond exact-field matching and the
    ``$set`` / ``$lt`` / ``$gt`` operators) are not implemented, but enough is
    provided to make the application's test suite work without a live database.
    """

    def __init__(self) -> None:
        self._docs: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _matches(self, doc: Dict[str, Any], filter: Dict[str, Any]) -> bool:
        """Return True if *doc* satisfies every field in *filter*."""
        for key, value in filter.items():
            if isinstance(value, dict):
                # Handle a small subset of MongoDB query operators
                for op, operand in value.items():
                    field_val = doc.get(key)
                    if op == "$lt" and not (field_val is not None and field_val < operand):
                        return False
                    elif op == "$lte" and not (field_val is not None and field_val <= operand):
                        return False
                    elif op == "$gt" and not (field_val is not None and field_val > operand):
                        return False
                    elif op == "$gte" and not (field_val is not None and field_val >= operand):
                        return False
                    elif op == "$ne" and doc.get(key) == operand:
                        return False
            else:
                if doc.get(key) != value:
                    return False
        return True

    def _apply_sort(
        self,
        docs: List[Dict[str, Any]],
        sort: List[Tuple[str, int]],
    ) -> List[Dict[str, Any]]:
        result = list(docs)
        for key, direction in reversed(sort):
            result.sort(
                key=lambda d: (d.get(key) is None, d.get(key)),
                reverse=(direction == -1),
            )
        return result

    def _apply_projection(
        self,
        doc: Dict[str, Any],
        projection: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not projection:
            return copy.deepcopy(doc)
        include = {k for k, v in projection.items() if v}
        exclude = {k for k, v in projection.items() if not v}
        if include:
            return {k: v for k, v in doc.items() if k in include}
        return {k: v for k, v in doc.items() if k not in exclude}

    # ------------------------------------------------------------------
    # AbstractRepository implementation
    # ------------------------------------------------------------------

    async def find_one(
        self,
        filter: Dict[str, Any],
        sort: Optional[List[Tuple[str, int]]] = None,
    ) -> Optional[Dict[str, Any]]:
        candidates = [d for d in self._docs if self._matches(d, filter)]
        if sort:
            candidates = self._apply_sort(candidates, sort)
        return copy.deepcopy(candidates[0]) if candidates else None

    async def _find_gen(
        self,
        filter: Optional[Dict[str, Any]],
        sort: Optional[List[Tuple[str, int]]],
        projection: Optional[Dict[str, Any]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        candidates = [d for d in self._docs if self._matches(d, filter or {})]
        if sort:
            candidates = self._apply_sort(candidates, sort)
        for doc in candidates:
            yield self._apply_projection(doc, projection)

    def find(
        self,
        filter: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, int]]] = None,
        projection: Optional[Dict[str, Any]] = None,
    ):
        return self._find_gen(filter, sort, projection)

    async def count_documents(
        self,
        filter: Optional[Dict[str, Any]] = None,
    ) -> int:
        return sum(1 for d in self._docs if self._matches(d, filter or {}))

    async def insert_one(
        self,
        document: Dict[str, Any],
    ) -> InsertOneResult:
        doc = copy.deepcopy(document)
        doc.setdefault("_id", str(uuid4()))
        self._docs.append(doc)
        return InsertOneResult(inserted_id=doc["_id"])

    async def insert_many(
        self,
        documents: List[Dict[str, Any]],
    ) -> InsertManyResult:
        ids: List[str] = []
        for document in documents:
            result = await self.insert_one(document)
            ids.append(result.inserted_id)
        return InsertManyResult(inserted_ids=ids)

    async def update_one(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
    ) -> UpdateResult:
        for i, doc in enumerate(self._docs):
            if self._matches(doc, filter):
                if "$set" in update:
                    self._docs[i].update(update["$set"])
                if "$unset" in update:
                    for key in update["$unset"]:
                        self._docs[i].pop(key, None)
                return UpdateResult(matched_count=1, modified_count=1)
        return UpdateResult(matched_count=0, modified_count=0)

    async def delete_one(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        for i, doc in enumerate(self._docs):
            if self._matches(doc, filter):
                del self._docs[i]
                return DeleteResult(deleted_count=1)
        return DeleteResult(deleted_count=0)

    async def delete_many(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        before = len(self._docs)
        self._docs = [d for d in self._docs if not self._matches(d, filter)]
        return DeleteResult(deleted_count=before - len(self._docs))

    async def create_index(
        self,
        keys: Union[str, List[Tuple[str, int]]],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        # No-op for in-memory store; uniqueness is not enforced here
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.mark.asyncio
async def test_insert_one_and_find_one(repo: InMemoryRepository):
    result = await repo.insert_one({"name": "alice", "score": 10})
    assert result.inserted_id

    doc = await repo.find_one({"name": "alice"})
    assert doc is not None
    assert doc["name"] == "alice"
    assert doc["score"] == 10


@pytest.mark.asyncio
async def test_find_one_returns_none_when_missing(repo: InMemoryRepository):
    doc = await repo.find_one({"name": "nobody"})
    assert doc is None


@pytest.mark.asyncio
async def test_find_iterates_matching_documents(repo: InMemoryRepository):
    await repo.insert_many([
        {"label": "hello", "val": 1},
        {"label": "hello", "val": 2},
        {"label": "world", "val": 3},
    ])
    docs = [d async for d in repo.find({"label": "hello"})]
    assert len(docs) == 2
    assert all(d["label"] == "hello" for d in docs)


@pytest.mark.asyncio
async def test_find_with_sort(repo: InMemoryRepository):
    await repo.insert_many([
        {"ts": 3}, {"ts": 1}, {"ts": 2}
    ])
    docs = [d async for d in repo.find(sort=[("ts", 1)])]
    assert [d["ts"] for d in docs] == [1, 2, 3]

    docs_desc = [d async for d in repo.find(sort=[("ts", -1)])]
    assert [d["ts"] for d in docs_desc] == [3, 2, 1]


@pytest.mark.asyncio
async def test_find_with_projection(repo: InMemoryRepository):
    await repo.insert_one({"a": 1, "b": 2, "c": 3})
    docs = [d async for d in repo.find(projection={"a": 1})]
    assert len(docs) == 1
    assert "a" in docs[0]
    assert "b" not in docs[0]


@pytest.mark.asyncio
async def test_count_documents(repo: InMemoryRepository):
    await repo.insert_many([{"x": 1}, {"x": 2}, {"x": 1}])
    assert await repo.count_documents({"x": 1}) == 2
    assert await repo.count_documents({}) == 3


@pytest.mark.asyncio
async def test_insert_many(repo: InMemoryRepository):
    result = await repo.insert_many([{"n": 1}, {"n": 2}, {"n": 3}])
    assert len(result.inserted_ids) == 3
    assert await repo.count_documents({}) == 3


@pytest.mark.asyncio
async def test_update_one(repo: InMemoryRepository):
    await repo.insert_one({"session_id": "s1", "label": "old"})

    result = await repo.update_one(
        {"session_id": "s1"},
        {"$set": {"label": "new"}},
    )
    assert result.matched_count == 1
    assert result.modified_count == 1

    doc = await repo.find_one({"session_id": "s1"})
    assert doc["label"] == "new"


@pytest.mark.asyncio
async def test_update_one_no_match(repo: InMemoryRepository):
    result = await repo.update_one({"session_id": "missing"}, {"$set": {"x": 1}})
    assert result.matched_count == 0
    assert result.modified_count == 0


@pytest.mark.asyncio
async def test_delete_one(repo: InMemoryRepository):
    await repo.insert_many([{"k": "a"}, {"k": "b"}])
    result = await repo.delete_one({"k": "a"})
    assert result.deleted_count == 1
    assert await repo.count_documents({}) == 1


@pytest.mark.asyncio
async def test_delete_many(repo: InMemoryRepository):
    await repo.insert_many([{"tag": "x"}, {"tag": "x"}, {"tag": "y"}])
    result = await repo.delete_many({"tag": "x"})
    assert result.deleted_count == 2
    assert await repo.count_documents({}) == 1


@pytest.mark.asyncio
async def test_create_index_noop(repo: InMemoryRepository):
    # create_index is a no-op for in-memory; just ensure it doesn't raise
    await repo.create_index("email", unique=True, name="email_unique")
    await repo.create_index([("session_id", 1)])


@pytest.mark.asyncio
async def test_lt_operator(repo: InMemoryRepository):
    await repo.insert_many([{"ts": 1}, {"ts": 5}, {"ts": 10}])
    docs = [d async for d in repo.find({"ts": {"$lt": 6}})]
    assert len(docs) == 2


def test_in_memory_repo_is_abstract_repository():
    """InMemoryRepository must satisfy the AbstractRepository interface."""
    assert issubclass(InMemoryRepository, AbstractRepository)
    repo = InMemoryRepository()
    assert isinstance(repo, AbstractRepository)
