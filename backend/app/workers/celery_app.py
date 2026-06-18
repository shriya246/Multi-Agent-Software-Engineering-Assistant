from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "codepilot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_default_queue="codepilot",
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
)
