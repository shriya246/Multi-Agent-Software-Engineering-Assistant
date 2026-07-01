from __future__ import annotations

from celery import Celery

from app.core.config import Settings, get_settings


def build_celery_app(settings: Settings) -> Celery:
    app = Celery(
        "codepilot",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )
    app.conf.update(
        task_default_queue="codepilot",
        task_default_exchange="codepilot",
        task_default_exchange_type="direct",
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_time_limit=settings.celery_task_time_limit_seconds,
        task_soft_time_limit=settings.celery_task_soft_time_limit_seconds,
        task_acks_late=True,
        task_acks_on_failure_or_timeout=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
        result_expires=settings.celery_result_expires_seconds,
        broker_connection_retry_on_startup=True,
        worker_send_task_events=True,
        task_send_sent_event=True,
        broker_transport_options={"visibility_timeout": settings.celery_task_time_limit_seconds},
        beat_schedule={
            "cleanup-stale-artifacts": {
                "task": "app.workers.tasks.cleanup_stale_artifacts",
                "schedule": 3600.0,
            }
        },
    )
    from app.workers import tasks

    app.task(name="app.workers.tasks.ping")(tasks.ping)
    app.task(name="app.workers.tasks.cleanup_stale_artifacts")(tasks.cleanup_stale_artifacts)
    app.task(name="app.workers.tasks.ingest_repository")(tasks.ingest_repository)
    app.task(name="app.workers.tasks.cleanup_repository_workspace")(
        tasks.cleanup_repository_workspace
    )
    return app


celery_app = build_celery_app(get_settings())
