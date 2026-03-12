import os
import logging
from celery import Celery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("signglove.worker")

# Load configuration from environment
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Initialize Celery app
celery_app = Celery(
    "signglove_v3",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["workers.tasks.dataset_tasks"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour max
)

if __name__ == "__main__":
    celery_app.start()
