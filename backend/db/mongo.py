"""
MongoDB collection access for local/offline development in the sign glove system.

Re-exports sensor_collection and sensor_repo from core.database to avoid
creating a second connection pool for the same database.

Prefer :func:`get_sensor_repository` for new code – it returns a
:class:`~db.repository.AbstractRepository` instance so callers remain
decoupled from the Motor driver.
"""
from core.database import sensor_collection, sensor_repo  # noqa: F401
from db.repository import AbstractRepository


def get_sensor_collection():
    """
    Returns the raw Motor sensor_data collection.

    .. deprecated::
        Prefer :func:`get_sensor_repository` for new code.
    """
    return sensor_collection


def get_sensor_repository() -> AbstractRepository:
    """
    Returns an :class:`~db.repository.AbstractRepository` for sensor data.

    Using this function instead of importing the Motor collection directly
    keeps callers decoupled from the underlying database driver, making it
    easier to swap MongoDB for another backend in the future.
    """
    return sensor_repo
