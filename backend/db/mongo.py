"""
MongoDB connection setup for local/offline development in the sign glove system.

- Connects to a local MongoDB instance (localhost:27017).
- Provides access to the sensor_data collection.
- Includes utility to create indexes for efficient queries.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from core.settings import settings
import logging

client = AsyncIOMotorClient(settings.MONGO_URI)
db = client[settings.DB_NAME]
sensor_collection = db["sensor_data"]

def get_sensor_collection():
    """
    Returns the sensor_data collection from the local MongoDB instance.
    """
    return sensor_collection

# Add this function to create indexes on startup
async def create_indexes():
    """
    Create indexes on the sensor_data collection for efficient querying.
    Indexes: session_id, _timestamp.
    """
    try:
        await sensor_collection.create_index("session_id")
        await sensor_collection.create_index("_timestamp")
    except Exception as e:
        logging.error(f"Failed to create indexes: {e}")
        raise