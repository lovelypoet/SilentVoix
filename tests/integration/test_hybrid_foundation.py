import asyncio
import uuid
import pytest
import httpx
from datetime import datetime, timezone
from sqlalchemy import text, select, pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from db.models import User, Dataset, Model, Base
from api.core.database import sensor_collection, prediction_collection
from api.core.settings import settings

# --- Special Test Engine (NullPool to avoid loop issues) ---
test_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=pool.NullPool
)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest.mark.asyncio
async def test_postgres_user_resilience():
    """Harshly test User CRUD and constraints in PostgreSQL."""
    print("\n[H] Testing PostgreSQL User Resilience...")
    email = f"harsh_test_{uuid.uuid4().hex[:8]}@example.com"
    
    async with TestSessionLocal() as session:
        # 1. Create User
        new_user = User(
            email=email,
            hashed_password="fake_hash_123",
            role="editor",
            full_name="Harsh Tester"
        )
        session.add(new_user)
        await session.commit()
        
        # 2. Read User
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one()
        assert user.email == email
        assert user.role == "editor"

        # 3. Unique Constraint Violation
        duplicate_user = User(
            email=email,
            hashed_password="another_hash"
        )
        session.add(duplicate_user)
        try:
            await session.commit()
            pytest.fail("Should have raised IntegrityError")
        except Exception:
            await session.rollback()
            print("   - Unique Constraint Verified")

@pytest.mark.asyncio
async def test_mongodb_sensor_data_flood():
    """Flood MongoDB with sensor data linked to a Postgres-defined Dataset."""
    print("\n[H] Testing MongoDB Sensor Data Flood & Linkage...")
    dataset_id = str(uuid.uuid4())
    
    batch = []
    for i in range(500):
        batch.append({
            "session_id": dataset_id,
            "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000) + i,
            "values": [float(v) for v in range(11)],
            "source": "harsh_flood_test"
        })
    
    result = await sensor_collection.insert_many(batch)
    assert len(result.inserted_ids) == 500
    print(f"   - Flooded MongoDB with 500 frames for ID: {dataset_id}")
    
    start_time = datetime.now()
    count = await sensor_collection.count_documents({"session_id": dataset_id})
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds() * 1000
    
    assert count == 500
    print(f"   - Retrieved 500 frames in {duration:.2f}ms")

@pytest.mark.asyncio
async def test_hybrid_jsonb_integrity():
    """Test PostgreSQL JSONB for complex, nested metadata artifacts."""
    print("\n[H] Testing PostgreSQL JSONB Integrity...")
    
    async with TestSessionLocal() as session:
        user = User(email=f"meta_{uuid.uuid4().hex[:6]}@test.com", hashed_password="pw")
        session.add(user)
        await session.commit()

        complex_meta = {
            "normalization": {"type": "min-max", "range": [0, 1]},
            "hyperparameters": {"layers": [64, 128, 64], "dropout": 0.25}
        }

        dataset = Dataset(
            name="Complex Dataset",
            storage_path="/path/to/data",
            modality="fusion",
            hand_mode="dual",
            owner_id=user.id,
            metadata_json=complex_meta
        )
        session.add(dataset)
        await session.commit()
        
        stmt = select(Dataset).where(Dataset.owner_id == user.id)
        result = await session.execute(stmt)
        ds = result.scalar_one()
        assert ds.metadata_json["hyperparameters"]["dropout"] == 0.25
        print("   - Complex JSONB Metadata Integrity Verified")

@pytest.mark.asyncio
async def test_api_lifespan_hybrid_health():
    """Ultimate Hybrid Check: test_connection() logic."""
    print("\n[H] Testing API Health under Hybrid DB load...")
    from api.core.database import test_connection
    await test_connection()
    print("   - Hybrid Connection Test Passed")

if __name__ == "__main__":
    # To run manually: ./venv/bin/python3 tests/integration/test_hybrid_foundation.py
    import asyncio
    asyncio.run(test_postgres_user_resilience())
    asyncio.run(test_mongodb_sensor_data_flood())
    asyncio.run(test_hybrid_jsonb_integrity())
    asyncio.run(test_api_lifespan_hybrid_health())
