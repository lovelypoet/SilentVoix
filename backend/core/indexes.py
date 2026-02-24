"""
Indexes setup for the sign glove system.

Uses the :class:`~db.repository.AbstractRepository` interface so that index
creation is decoupled from the underlying database driver.  If a collection
is later migrated to a different backend, only ``core.database`` needs to be
updated – this module continues to work unchanged.
"""
from core.database import (
    sensor_repo,
    model_repo,
    gesture_repo,
    training_repo,
    users_repo,
    voice_repo,
)

async def create_indexes():
    """
    Create indexes on key fields for all main collections to optimize query performance.
    """
    # Sensor data
    await sensor_repo.create_index("session_id")
    await sensor_repo.create_index("gesture_label")
    await sensor_repo.create_index("timestamp")

    # Model results
    await model_repo.create_index("model_name")

    # Training sessions
    await training_repo.create_index("model_name")
    await training_repo.create_index("started_at")

    # Gestures (optional — only if needed)
    await gesture_repo.create_index("session_id")
    await gesture_repo.create_index("label")

    # Users — unique constraint on email to prevent duplicate accounts
    await users_repo.create_index(
        [("email", 1)], unique=True, name="users_email_unique"
    )

    # Voice data
    await voice_repo.create_index("session_id")
    await voice_repo.create_index("timestamp")
