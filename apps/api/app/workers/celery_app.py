"""Phase 3.1 最小 Celery 应用配置。"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "junhui",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"])
