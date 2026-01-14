"""
Database connection and collection setup for the sign glove system.

- Sets up MongoDB client and main collections (predictions, sensor_data, model_results, gestures, training_sessions).
- Provides async test_connection function to verify MongoDB connectivity.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from core.settings import settings
import logging

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(settings.MONGO_URI, w=1)

if settings.ENVIRONMENT == "testing":
    db = client[settings.TEST_DB_NAME]
else:
    db = client[settings.DB_NAME]

# Collections
sensor_collection = db.sensor_data
prediction_collection = db.predictions
model_collection = db.model_results
gesture_collection = db.gestures
training_collection = db.training_sessions
users_collection = db.users
voice_collection = db.voice_data

"""
    Test the MongoDB connection by sending a ping command.
    Logs success or failure.
    """

async def test_connection():
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB Atlas!")
    except Exception as e:
        logger.error("MongoDB connection failed:", exc_info=e)
