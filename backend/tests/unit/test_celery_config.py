from __future__ import annotations

from app.core.config import Settings
from app.workers.celery_app import build_celery_app


def test_celery_configuration_uses_json_only() -> None:
    app = build_celery_app(Settings(redis_url="redis://localhost:6379/0"))
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
    assert app.conf.accept_content == ["json"]
    assert app.conf.worker_prefetch_multiplier == 1
    assert app.tasks["app.workers.tasks.ping"].name == "app.workers.tasks.ping"
