"""
Indexes setup for MongoDB collections in the sign glove system.

- create_indexes: Ensures indexes exist for efficient queries on sensor, model,
  training, gesture, user, and voice collections.
"""
from core.database import (
    sensor_collection,
    model_collection,
    gesture_collection,
    training_collection,
    users_collection,
    voice_collection,
)

async def create_indexes():
    """
    Create indexes on key fields for all main collections to optimize query performance.
    """
    # Sensor data
    await sensor_collection.create_index("session_id")
    await sensor_collection.create_index("gesture_label")
    await sensor_collection.create_index("timestamp")

    # Model results
    await model_collection.create_index("model_name")

    # Training sessions
    await training_collection.create_index("model_name")
    await training_collection.create_index("started_at")

    # Gestures (optional — only if needed)
    await gesture_collection.create_index("session_id")
    await gesture_collection.create_index("label")

    # Users — unique constraint on email to prevent duplicate accounts
    await users_collection.create_index(
        [("email", 1)], unique=True, name="users_email_unique"
    )

    # Voice data
    await voice_collection.create_index("session_id")
    await voice_collection.create_index("timestamp")
