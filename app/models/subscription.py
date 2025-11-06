from sqlalchemy import Column, Integer, String, Boolean
from app.db.database import Base


class Subscription(Base):
    """
    Модель таблицы подписок VPN сервиса.
    """
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, nullable=False, index=True, unique=True)
    password = Column(String, nullable=False)
    active = Column(Boolean, nullable=False, default=True)  # Активна ли подписка
    link = Column(String, nullable=True)  # Ссылка

    def __repr__(self):
        return f"<Subscription(username='{self.username}', active={self.active})>"

