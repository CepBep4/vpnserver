from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import base, auth, subscriptions
from app.db.database import init_db
import logging

# Базовая конфигурация логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Создаем экземпляр FastAPI приложения
app = FastAPI(
    title="VPN Server API",
    description="API для VPN сервера с документацией Swagger",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc альтернативная документация
    openapi_url="/openapi.json"  # OpenAPI схема
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключение роутеров
app.include_router(base.router)
app.include_router(auth.router)  # Эндпоинт /login доступен без токена
app.include_router(subscriptions.router)  # Эндпоинты подписок защищены токеном


@app.on_event("startup")
async def startup_event():
    """
    Инициализация при запуске приложения.
    """
    # Инициализация базы данных
    init_db()
    logging.info("База данных инициализирована")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Действия при остановке приложения.
    """
    logging.info("Приложение остановлено")

