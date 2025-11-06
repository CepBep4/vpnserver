from celery import Celery
from celery.schedules import crontab
import os
import logging

# Базовая конфигурация логирования (если ещё не настроено)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Создаем экземпляр Celery
celery_app = Celery(
    "vpnserver",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Настройка расписания для периодических задач
    beat_schedule={
        "check-subscriptions": {
            "task": "app.tasks.subscription.check_subscriptions",
            "schedule": crontab(minute="*"),  # Каждую минуту
        },
    },
)

# Импортируем задачи для их регистрации
from app.tasks import subscription  # noqa: F401

