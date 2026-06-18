from __future__ import annotations

from app.workers.celery_app import celery_app


def ping() -> str:
    return "pong"


ping = celery_app.task(name="app.workers.tasks.ping")(ping)
