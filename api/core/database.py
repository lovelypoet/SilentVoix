"""
Database connection and collection setup for the sign glove system.

- Sets up MongoDB client and main collections (predictions, sensor_data, model_results, gestures, training_sessions).
- Sets up SQLAlchemy engine for PostgreSQL (users, metadata).
- Provides async test functions to verify both MongoDB and PostgreSQL connectivity.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from api.core.settings import settings
import logging
from sqlalchemy import text
from db.base import engine as pg_engine

logger = logging.getLogger(__name__)

# --- MongoDB Setup ---
client = AsyncIOMotorClient(settings.MONGO_URI, w=1)

if settings.ENVIRONMENT == "testing":
    db = client[settings.TEST_DB_NAME]
else:
    db = client[settings.DB_NAME]

# Collections (ML/Sensor Data)
sensor_collection = db.sensor_data
prediction_collection = db.predictions
model_collection = db.model_results # Legacy
gestures_collection = db.gestures
training_collection = db.training_sessions
voice_collection = db.voice_data
feedback_collection = db.feedback

# --- Connection Tests ---

async def test_connection():
    """Test both MongoDB and PostgreSQL connectivity."""
    # Test MongoDB
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB!")
    except Exception as e:
        logger.error("MongoDB connection failed:", exc_info=e)

    # Test PostgreSQL
    try:
        async with pg_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL!")
    except Exception as e:
        logger.error("PostgreSQL connection failed:", exc_info=e)
