# src/tasks/celery_app.py

from celery import Celery
import os
from core.config import redis_config
from tasks import workers  # ✅ Explicit import to register tasks

broker_url = os.getenv("CELERY_BROKER_URL", redis_config.redis_url)
result_backend = os.getenv("CELERY_RESULT_BACKEND", redis_config.redis_url)

celery_app = Celery(
    "tasks",
    broker=broker_url,
    backend=result_backend,
    include=["tasks.workers"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
)
