from celery import Celery
import os

# Broker and backend (example using Redis)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "New_document_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

# Optional config
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

import app.services.task
