from fastapi import APIRouter, status
from pydantic import BaseModel
from datetime import datetime
from typing import Dict
from sqlalchemy import text
from app.db.database import SessionLocal
from app.models.subscription import Subscription
from app.services.xray_manager import read_xray_config
import subprocess
import redis

router = APIRouter(
    tags=["base"]
)

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    message: str


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Проверка здоровья сервиса",
    description="Эндпоинт для проверки работоспособности сервиса"
)
async def health_check():
    """
    Проверка здоровья сервиса.
    
    Возвращает статус сервиса и текущее время.
    Этот эндпоинт не требует аутентификации.
    """
    return HealthResponse(
        status="ok",
        timestamp=datetime.now(),
        message="Сервис работает нормально"
    )


def check_xray_status() -> tuple[str, str]:
    """Проверяет статус Xray сервиса."""
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "xray"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if result.returncode == 0:
            status = result.stdout.strip()
            if status == "active":
                return "active", "Xray сервис работает"
            else:
                return status, f"Xray сервис в статусе: {status}"
        else:
            return "unknown", "Не удалось определить статус Xray"
    except Exception as e:
        return "error", f"Ошибка проверки Xray: {str(e)}"


def check_redis_status() -> tuple[str, str]:
    """Проверяет статус Redis."""
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=2)
        r.ping()
        return "connected", "Redis доступен и работает"
    except redis.ConnectionError:
        return "disconnected", "Redis недоступен"
    except Exception as e:
        return "error", f"Ошибка подключения к Redis: {str(e)}"


def count_xray_users() -> tuple[int, str]:
    """Подсчитывает количество пользователей в Xray конфигурации."""
    try:
        config = read_xray_config()
        if not config:
            return 0, "Конфигурация Xray не найдена"
        
        inbounds = config.get("inbounds", [])
        if not inbounds:
            return 0, "В конфигурации Xray отсутствуют inbound-настройки"
        clients = inbounds[0].get("settings", {}).get("clients", [])
        count = len(clients)
        return count, f"Найдено {count} пользователей в конфигурации Xray"
    except Exception as e:
        return 0, f"Ошибка чтения конфигурации Xray: {str(e)}"


@router.get(
    "/metrics",
    status_code=status.HTTP_200_OK,
    summary="Метрики системы",
    description="Возвращает метрики системы в формате JSON"
)
async def get_metrics():
    """
    Возвращает метрики системы VPN сервера.
    
    Включает:
    - Статистику пользователей (всего, активных, неактивных, без ссылок)
    - Статус сервисов (Xray, Redis, база данных)
    - Количество пользователей в Xray конфигурации
    
    Этот эндпоинт не требует аутентификации.
    """
    db = SessionLocal()
    metrics: Dict[str, Dict[str, str]] = {}
    
    try:
        # Статистика пользователей
        all_users = db.query(Subscription).all()
        total_users = len(all_users)
        active_users = len([u for u in all_users if u.active])
        inactive_users = total_users - active_users
        users_without_link = len([u for u in all_users if not u.link])
        users_with_link = total_users - users_without_link
        
        metrics["total_users"] = {
            "val": str(total_users),
            "comment": "Общее количество пользователей в базе данных"
        }
        
        metrics["active_users"] = {
            "val": str(active_users),
            "comment": "Количество активных пользователей (active=True)"
        }
        
        metrics["inactive_users"] = {
            "val": str(inactive_users),
            "comment": "Количество неактивных пользователей (active=False)"
        }
        
        metrics["users_without_link"] = {
            "val": str(users_without_link),
            "comment": "Количество пользователей без VLESS ссылки"
        }
        
        metrics["users_with_link"] = {
            "val": str(users_with_link),
            "comment": "Количество пользователей с VLESS ссылкой"
        }
        
        # Статус Xray
        xray_status, xray_comment = check_xray_status()
        metrics["xray_status"] = {
            "val": xray_status,
            "comment": xray_comment
        }
        
        # Статус Redis
        redis_status, redis_comment = check_redis_status()
        metrics["redis_status"] = {
            "val": redis_status,
            "comment": redis_comment
        }
        
        # Статус базы данных
        try:
            db.execute(text("SELECT 1"))
            db_status = "connected"
            db_comment = "База данных доступна и работает"
        except Exception as e:
            db_status = "error"
            db_comment = f"Ошибка подключения к базе данных: {str(e)}"
        
        metrics["database_status"] = {
            "val": db_status,
            "comment": db_comment
        }
        
        # Количество пользователей в Xray
        xray_users_count, xray_users_comment = count_xray_users()
        metrics["xray_users_count"] = {
            "val": str(xray_users_count),
            "comment": xray_users_comment
        }
        
        # Timestamp
        metrics["timestamp"] = {
            "val": datetime.now().isoformat(),
            "comment": "Время сбора метрик (ISO 8601)"
        }
        
    except Exception as e:
        metrics["error"] = {
            "val": "error",
            "comment": f"Ошибка при сборе метрик: {str(e)}"
        }
    finally:
        db.close()
    
    return metrics
