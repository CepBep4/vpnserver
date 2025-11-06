import uuid
import urllib.parse
from app.models.subscription import Subscription
from app.core.config import settings
from app.services.xray_manager import add_user_to_xray, remove_user_from_xray, is_user_in_xray


def generate_uuid_from_credentials(username: str, password: str) -> str:
    """
    Генерирует детерминированный UUID из username и password.
    Одинаковые username и password всегда дают одинаковый UUID.
    
    Args:
        username: имя пользователя
        password: пароль пользователя
        
    Returns:
        UUID в формате строки
    """
    # Используем namespace UUID для детерминированной генерации
    # Комбинируем username и password для создания уникального идентификатора
    combined = f"{username}:{password}"
    # Используем UUID5 для детерминированной генерации
    namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # UUID namespace для URL
    user_uuid = uuid.uuid5(namespace, combined)
    return str(user_uuid)


def generate_vless_link(user_uuid: str, username: str) -> str:
    """
    Генерирует VLESS ссылку для пользователя с Reality.
    Использует имя из конфига (VPN_NAME).
    
    VLESS формат:
    vless://{uuid}@{host}:{port}?type=tcp&security=reality&pbk={publicKey}&fp={fingerprint}&sni={serverName}&sid={shortId}&encryption=none#{remark}
    """
    # Используем ту же функцию что и для генерации только ссылки
    return generate_vless_link_only(user_uuid)


def generate_vless_link_only(user_uuid: str) -> str:
    """
    Генерирует только VLESS ссылку без добавления пользователя в Xray.
    Используется для получения ссылки существующего пользователя.
    
    Args:
        user_uuid: UUID пользователя
        
    Returns:
        VLESS ссылка с правильным именем из конфига
    """
    # Параметры VLESS с Reality
    vless_type = "tcp"
    security = "reality"
    encryption = "none"
    
    # Используем оригинальное имя VPN с эмодзи и правильно кодируем для URL
    remark = settings.VPN_NAME
    # Кодируем имя для корректного использования в URL (эмодзи будут правильно закодированы)
    remark_encoded = urllib.parse.quote(remark, safe='')
    
    # Формируем VLESS ссылку с Reality параметрами
    vless_link = (
        f"vless://{user_uuid}@{settings.VPN_SERVER_HOST}:{settings.VPN_SERVER_PORT}"
        f"?type={vless_type}&security={security}"
        f"&pbk={settings.REALITY_PUBLIC_KEY}"
        f"&fp={settings.REALITY_FINGERPRINT}"
        f"&sni={settings.REALITY_SERVER_NAME}"
        f"&sid={settings.REALITY_SHORT_ID}"
        f"&encryption={encryption}#{remark_encoded}"
    )
    
    return vless_link


def create_vless_profile(subscription: Subscription) -> tuple[str, str]:
    """
    Создает VLESS профиль для пользователя.
    
    Returns:
        tuple: (vless_link, uuid)
    """
    # Извлекаем UUID из существующей ссылки или генерируем новый
    if subscription.link:
        user_uuid = extract_uuid_from_link(subscription.link)
        if not user_uuid:
            # Если не удалось извлечь UUID, генерируем новый
            user_uuid = str(uuid.uuid4())
    else:
        user_uuid = str(uuid.uuid4())
    
    # Если пользователя нет в Xray, добавляем его
    if not is_user_in_xray(user_uuid):
        email = f"{subscription.username}@sunstrikevpn.local"
        if add_user_to_xray(user_uuid, email):
            print(f"Пользователь {subscription.username} добавлен в Xray конфигурацию")
        else:
            print(f"Предупреждение: не удалось добавить пользователя {subscription.username} в Xray")
    
    # Всегда генерируем новую ссылку в актуальном формате Reality
    # Это гарантирует, что ссылка всегда соответствует текущей конфигурации
    link = generate_vless_link(user_uuid, subscription.username)
    
    print(f"Создан VLESS профиль (Reality) для пользователя {subscription.username}")
    print(f"UUID: {user_uuid}")
    print(f"Ссылка: {link}")
    
    return link, user_uuid


def disable_vless_profile(subscription: Subscription):
    """
    Отключает VLESS профиль пользователя.
    """
    if not subscription.link:
        print(f"Предупреждение: ссылка для пользователя {subscription.username} отсутствует")
        return
    
    user_uuid = extract_uuid_from_link(subscription.link)
    
    if not user_uuid:
        print(f"Ошибка: не удалось извлечь UUID из ссылки для {subscription.username}")
        return
    
    # Удаляем пользователя из Xray конфигурации
    if remove_user_from_xray(user_uuid):
        print(f"Пользователь {subscription.username} удален из Xray конфигурации")
    else:
        print(f"Предупреждение: не удалось удалить пользователя {subscription.username} из Xray")


def extract_uuid_from_link(link: str) -> str:
    """
    Извлекает UUID из VLESS ссылки.
    """
    if not link or not link.startswith("vless://"):
        return ""
    
    try:
        # Формат: vless://uuid@host:port?...
        uuid_part = link.split("://")[1].split("@")[0]
        return uuid_part
    except Exception:
        return ""

