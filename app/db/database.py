from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Путь к базе данных SQLite
DATABASE_URL = "sqlite:///./vpnserver.db"

# Создаем движок SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Необходимо для SQLite
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()


def get_db():
    """
    Генератор для получения сессии базы данных.
    Используется как зависимость в FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Инициализация базы данных - создание всех таблиц.
    """
    # Импортируем модели чтобы они зарегистрировались в Base.metadata
    from app.models import Subscription  # noqa: F401
    Base.metadata.create_all(bind=engine)

