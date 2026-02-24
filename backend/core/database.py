"""
Database connection and collection setup for the sign glove system.

- Sets up MongoDB client and main collections (predictions, sensor_data,
  model_results, gestures, training_sessions).
- Wraps each collection in a :class:`~db.mongo_repository.MongoRepository`
  so that route and service code can depend on the
  :class:`~db.repository.AbstractRepository` interface rather than on
  Motor-specific objects, making future migration to a different database
  backend (e.g. PostgreSQL) straightforward.
- Provides async test_connection function to verify MongoDB connectivity.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from core.settings import settings
from db.mongo_repository import MongoRepository
import logging

logger = logging.getLogger(__name__)

client = AsyncIOMotorClient(settings.MONGO_URI, w=1)

if settings.ENVIRONMENT == "testing":
    db = client[settings.TEST_DB_NAME]
else:
    db = client[settings.DB_NAME]

# ---------------------------------------------------------------------------
# Raw Motor collections (kept for backward compatibility with existing code
# that imports them directly).  Prefer the repository instances below for
# new code.
# ---------------------------------------------------------------------------
sensor_collection = db.sensor_data
prediction_collection = db.predictions
model_collection = db.model_results
gesture_collection = db.gestures
training_collection = db.training_sessions
users_collection = db.users
voice_collection = db.voice_data

# ---------------------------------------------------------------------------
# Repository instances – database-agnostic interface
#
# These wrap the Motor collections above and expose
# :class:`~db.repository.AbstractRepository` methods.  Swap the
# ``MongoRepository`` constructor call for another
# ``AbstractRepository`` subclass (e.g. ``PostgresRepository``) to
# migrate a collection to a different backend without touching routes.
# ---------------------------------------------------------------------------
sensor_repo: MongoRepository = MongoRepository(sensor_collection)
prediction_repo: MongoRepository = MongoRepository(prediction_collection)
model_repo: MongoRepository = MongoRepository(model_collection)
gesture_repo: MongoRepository = MongoRepository(gesture_collection)
training_repo: MongoRepository = MongoRepository(training_collection)
users_repo: MongoRepository = MongoRepository(users_collection)
voice_repo: MongoRepository = MongoRepository(voice_collection)


async def test_connection():
    """Test the MongoDB connection by sending a ping command.
    Logs success or failure.
    """
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB Atlas!")
    except Exception as e:
        logger.error("MongoDB connection failed:", exc_info=e)
