"""
PostgreSQL implementation of :class:`~db.repository.AbstractRepository`
using SQLAlchemy 2 async (ORM-free, Core only) with a JSONB data column.

Migration strategy
------------------
Each logical MongoDB collection maps to a single PostgreSQL table::

    CREATE TABLE <collection> (
        id      BIGSERIAL PRIMARY KEY,
        data    JSONB NOT NULL DEFAULT '{}'
    );

All document fields live inside the ``data`` JSONB column, so no schema
changes are needed when the document shape evolves.  Indexes are created as
PostgreSQL expression indexes on JSONB paths.

Usage
-----
Provide a SQLAlchemy async engine and a table name when constructing the
repository::

    from sqlalchemy.ext.asyncio import create_async_engine
    from db.sqlalchemy_repository import SQLAlchemyRepository

    engine = create_async_engine("postgresql+asyncpg://user:pass@host/db")
    sensor_repo = SQLAlchemyRepository(engine, table_name="sensor_data")

Then pass the repository wherever an :class:`~db.repository.AbstractRepository`
is expected.  No other code changes are required.

Installing dependencies
-----------------------
These packages are not included in the default ``requirements.txt`` because
they are only needed when migrating away from MongoDB::

    pip install "sqlalchemy[asyncio]==2.0.46" asyncpg==0.31.0

Note
----
The ``$set`` / ``$unset`` MongoDB update operators are translated to
standard SQL UPDATE statements.  More complex operators (``$inc``,
``$push``, etc.) raise :class:`NotImplementedError` and should be
implemented as the need arises.
"""
from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

from sqlalchemy import (
    BigInteger,
    Column,
    Index,
    MetaData,
    Table,
    Text,
    delete,
    func,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from db.repository import (
    AbstractRepository,
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)

# Shared metadata object; all dynamically-created tables are registered here.
_metadata = MetaData()


def _make_table(table_name: str) -> Table:
    """Return (and register in _metadata) a JSONB document table."""
    return Table(
        table_name,
        _metadata,
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("data", JSONB, nullable=False, server_default=text("'{}'")),
        # Allow multiple calls with the same name (idempotent)
        keep_existing=True,
    )


def _build_where_clause(table: Table, filter: Dict[str, Any]):
    """
    Translate a subset of MongoDB-style filter operators into a SQLAlchemy
    WHERE clause using PostgreSQL JSONB operators.

    Supported operators: exact match, ``$lt``, ``$lte``, ``$gt``, ``$gte``,
    ``$ne``.

    Example::

        {"label": "hello", "ts": {"$gt": 100}}
        → data->>'label' = 'hello' AND (data->>'ts')::numeric > 100
    """
    clauses = []
    for key, value in filter.items():
        col = table.c.data[key]
        if isinstance(value, dict):
            for op, operand in value.items():
                # Cast JSONB text to numeric for comparisons
                cast_col = func.cast(col.astext, Text).cast(
                    # Use a generic numeric cast via text() for portability
                    text("numeric")
                ) if isinstance(operand, (int, float)) else col.astext
                if op == "$lt":
                    clauses.append(cast_col < operand)
                elif op == "$lte":
                    clauses.append(cast_col <= operand)
                elif op == "$gt":
                    clauses.append(cast_col > operand)
                elif op == "$gte":
                    clauses.append(cast_col >= operand)
                elif op == "$ne":
                    clauses.append(col.astext != str(operand))
                else:
                    raise NotImplementedError(
                        f"Query operator '{op}' is not yet implemented "
                        "in SQLAlchemyRepository"
                    )
        else:
            clauses.append(col.astext == str(value))
    return clauses


class SQLAlchemyRepository(AbstractRepository):
    """PostgreSQL-backed repository using SQLAlchemy 2 async Core + JSONB.

    Each collection is represented as a single table with a ``data JSONB``
    column.  This preserves the document-oriented model while storing data
    in a relational database, making migration from MongoDB minimally
    disruptive.

    Parameters
    ----------
    engine:
        A SQLAlchemy :class:`~sqlalchemy.ext.asyncio.AsyncEngine` configured
        for PostgreSQL (``postgresql+asyncpg://...``).
    table_name:
        The PostgreSQL table name, typically matching the MongoDB collection
        name (e.g. ``"sensor_data"``, ``"users"``).
    """

    def __init__(self, engine: AsyncEngine, table_name: str) -> None:
        self._engine = engine
        self._table = _make_table(table_name)
        self._session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------

    async def init_table(self) -> None:
        """Create the table in the database if it does not already exist.

        Call this once at application startup (analogous to :meth:`create_index`
        initialising a MongoDB collection).
        """
        async with self._engine.begin() as conn:
            await conn.run_sync(_metadata.create_all)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _row_to_doc(self, row) -> Dict[str, Any]:
        """Convert a SQLAlchemy row to a plain dict, injecting ``_id``."""
        doc: Dict[str, Any] = dict(row.data)
        doc["_id"] = str(row.id)
        return doc

    # ------------------------------------------------------------------
    # AbstractRepository implementation
    # ------------------------------------------------------------------

    async def find_one(
        self,
        filter: Dict[str, Any],
        sort: Optional[List[Tuple[str, int]]] = None,
    ) -> Optional[Dict[str, Any]]:
        async with self._session_factory() as session:
            stmt = select(self._table)
            for clause in _build_where_clause(self._table, filter):
                stmt = stmt.where(clause)
            if sort:
                for field, direction in sort:
                    col = self._table.c.data[field].astext
                    stmt = stmt.order_by(col.asc() if direction == 1 else col.desc())
            stmt = stmt.limit(1)
            result = await session.execute(stmt)
            row = result.fetchone()
            return self._row_to_doc(row) if row else None

    async def _find_gen(
        self,
        filter: Optional[Dict[str, Any]],
        sort: Optional[List[Tuple[str, int]]],
        projection: Optional[Dict[str, Any]],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        async with self._session_factory() as session:
            stmt = select(self._table)
            for clause in _build_where_clause(self._table, filter or {}):
                stmt = stmt.where(clause)
            if sort:
                for field, direction in sort:
                    col = self._table.c.data[field].astext
                    stmt = stmt.order_by(col.asc() if direction == 1 else col.desc())
            result = await session.execute(stmt)
            for row in result.fetchall():
                doc = self._row_to_doc(row)
                if projection:
                    include = {k for k, v in projection.items() if v}
                    exclude = {k for k, v in projection.items() if not v}
                    if include:
                        doc = {k: v for k, v in doc.items() if k in include}
                    else:
                        doc = {k: v for k, v in doc.items() if k not in exclude}
                yield doc

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
        async with self._session_factory() as session:
            stmt = select(func.count()).select_from(self._table)
            for clause in _build_where_clause(self._table, filter or {}):
                stmt = stmt.where(clause)
            result = await session.execute(stmt)
            return result.scalar_one()

    async def insert_one(
        self,
        document: Dict[str, Any],
    ) -> InsertOneResult:
        async with self._session_factory() as session:
            stmt = (
                pg_insert(self._table)
                .values(data=document)
                .returning(self._table.c.id)
            )
            result = await session.execute(stmt)
            await session.commit()
            row_id = result.scalar_one()
            return InsertOneResult(inserted_id=str(row_id))

    async def insert_many(
        self,
        documents: List[Dict[str, Any]],
    ) -> InsertManyResult:
        async with self._session_factory() as session:
            stmt = (
                pg_insert(self._table)
                .values([{"data": doc} for doc in documents])
                .returning(self._table.c.id)
            )
            result = await session.execute(stmt)
            await session.commit()
            ids = [str(row[0]) for row in result.fetchall()]
            return InsertManyResult(inserted_ids=ids)

    async def update_one(
        self,
        filter: Dict[str, Any],
        update_doc: Dict[str, Any],
    ) -> UpdateResult:
        # Translate MongoDB update operators to JSONB merge / removal
        if "$set" in update_doc:
            set_fields: Dict[str, Any] = update_doc["$set"]
        elif "$unset" in update_doc:
            set_fields = {}
        else:
            raise NotImplementedError(
                "Only $set and $unset update operators are supported "
                "in SQLAlchemyRepository"
            )

        unset_keys: List[str] = list(update_doc.get("$unset", {}).keys())

        async with self._session_factory() as session:
            # Find the first matching row id
            sel = select(self._table.c.id)
            for clause in _build_where_clause(self._table, filter):
                sel = sel.where(clause)
            sel = sel.limit(1)
            res = await session.execute(sel)
            row = res.fetchone()
            if row is None:
                return UpdateResult(matched_count=0, modified_count=0)

            row_id = row[0]

            # Build new data: merge $set and remove $unset keys using JSONB
            # concatenation operator (||) and - operator
            new_data_expr = self._table.c.data
            if set_fields:
                new_data_expr = new_data_expr.op("||")(
                    func.cast(json.dumps(set_fields), JSONB)
                )
            for key in unset_keys:
                new_data_expr = new_data_expr.op("-")(key)

            stmt = (
                update(self._table)
                .where(self._table.c.id == row_id)
                .values(data=new_data_expr)
            )
            await session.execute(stmt)
            await session.commit()
            return UpdateResult(matched_count=1, modified_count=1)

    async def delete_one(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        async with self._session_factory() as session:
            sel = select(self._table.c.id)
            for clause in _build_where_clause(self._table, filter):
                sel = sel.where(clause)
            sel = sel.limit(1)
            res = await session.execute(sel)
            row = res.fetchone()
            if row is None:
                return DeleteResult(deleted_count=0)
            stmt = delete(self._table).where(self._table.c.id == row[0])
            await session.execute(stmt)
            await session.commit()
            return DeleteResult(deleted_count=1)

    async def delete_many(
        self,
        filter: Dict[str, Any],
    ) -> DeleteResult:
        async with self._session_factory() as session:
            stmt = delete(self._table)
            for clause in _build_where_clause(self._table, filter):
                stmt = stmt.where(clause)
            result = await session.execute(stmt)
            await session.commit()
            return DeleteResult(deleted_count=result.rowcount)

    async def create_index(
        self,
        keys: Union[str, List[Tuple[str, int]]],
        unique: bool = False,
        name: Optional[str] = None,
    ) -> None:
        """Create a PostgreSQL expression index on a JSONB path.

        For a single string key (e.g. ``"email"``), this creates::

            CREATE INDEX ON <table> ((data->>'email'));

        For compound keys (list of tuples), each field is included in a
        multi-column expression index.
        """
        if isinstance(keys, str):
            field_list = [(keys, 1)]
        else:
            field_list = keys

        index_cols = [
            self._table.c.data[field].astext for field, _ in field_list
        ]
        idx_name = name or "_".join(f for f, _ in field_list)
        idx = Index(
            f"{self._table.name}_{idx_name}_idx",
            *index_cols,
            unique=unique,
        )
        async with self._engine.begin() as conn:
            await conn.run_sync(idx.create, checkfirst=True)
