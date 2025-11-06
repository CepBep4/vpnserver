"""
Модуль конфигурации приложения.
Загружает настройки из файла CONF.py в корне проекта.
"""
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь для импорта CONF
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Импортируем настройки из CONF.py
try:
    import CONF
except ImportError:
    raise ImportError(
        "Не удалось импортировать CONF.py. Убедитесь, что файл CONF.py находится в корне проекта."
    )


class Settings:
    """
    Класс настроек приложения.
    Все значения загружаются из CONF.py
    """
    
    # JWT настройки
    SECRET_KEY: str = CONF.SECRET_KEY
    ALGORITHM: str = getattr(CONF, 'ALGORITHM', 'HS256')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = CONF.ACCESS_TOKEN_EXPIRE_MINUTES
    
    # Учетные данные администратора
    ADMIN_USERNAME: str = CONF.ADMIN_USERNAME
    ADMIN_PASSWORD: str = CONF.ADMIN_PASSWORD
    
    # VPN сервер настройки
    VPN_SERVER_HOST: str = CONF.VPN_SERVER_HOST
    VPN_SERVER_PORT: int = CONF.VPN_SERVER_PORT
    VPN_NAME: str = CONF.VPN_NAME
    
    # Xray Reality настройки
    REALITY_PRIVATE_KEY: str = CONF.REALITY_PRIVATE_KEY
    REALITY_PUBLIC_KEY: str = CONF.REALITY_PUBLIC_KEY
    REALITY_SERVER_NAME: str = CONF.REALITY_SERVER_NAME
    REALITY_SHORT_ID: str = CONF.REALITY_SHORT_ID
    REALITY_FINGERPRINT: str = CONF.REALITY_FINGERPRINT
    
    # Xray настройки
    XRAY_CONFIG_PATH: str = getattr(CONF, 'XRAY_CONFIG_PATH', '/usr/local/etc/xray/config.json')


# Создаем экземпляр настроек
settings = Settings()

