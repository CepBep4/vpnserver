from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Путь к базе данных SQLite
# В Docker используем /app/data для сохранения данных в volume
db_path = os.getenv("DATABASE_PATH", "./vpnserver.db")
if db_path.startswith("./"):
    # Если путь относительный, проверяем наличие директории data
    data_dir = os.getenv("DATA_DIR", "./data")
    if os.path.exists(data_dir) and os.path.isdir(data_dir):
        db_path = os.path.join(data_dir, "vpnserver.db")
    else:
        db_path = db_path.replace("./", "", 1)

DATABASE_URL = f"sqlite:///{db_path}"

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

