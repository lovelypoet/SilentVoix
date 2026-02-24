"""
MongoDB collection access for local/offline development in the sign glove system.

Re-exports sensor_collection from core.database to avoid creating a second
connection pool for the same database.
"""
from core.database import sensor_collection  # noqa: F401


def get_sensor_collection():
    """
    Returns the sensor_data collection.
    """
    return sensor_collection
