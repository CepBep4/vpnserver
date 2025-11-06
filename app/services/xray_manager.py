import json
import subprocess
import os
import logging
import time
import fcntl
from typing import Dict
from app.core.config import settings


XRAY_CONFIG_PATH = settings.XRAY_CONFIG_PATH
LOCK_PATH = XRAY_CONFIG_PATH + '.lock'


def read_xray_config() -> Dict:
    """Читает конфигурацию Xray из файла."""
    try:
        # Разделяемая блокировка на время чтения
        os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
        with open(LOCK_PATH, 'a+') as lockf:
            fcntl.flock(lockf, fcntl.LOCK_SH)
            try:
                with open(XRAY_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except FileNotFoundError:
                return {}
            except json.JSONDecodeError:
                return {}
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)
    except Exception as e:
        logging.error("Ошибка чтения конфигурации Xray: %s", e)
        return {}


def write_xray_config(config: Dict):
    """Записывает конфигурацию Xray в файл."""
    # Создаем временный файл для атомарной записи
    temp_path = XRAY_CONFIG_PATH + '.tmp'
    try:
        os.makedirs(os.path.dirname(XRAY_CONFIG_PATH), exist_ok=True)
        # Эксклюзивная блокировка на время записи
        with open(LOCK_PATH, 'a+') as lockf:
            fcntl.flock(lockf, fcntl.LOCK_EX)
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                # Атомарно заменяем файл (безусловная замена надёжнее os.rename)
                os.replace(temp_path, XRAY_CONFIG_PATH)
            finally:
                fcntl.flock(lockf, fcntl.LOCK_UN)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logging.exception("Ошибка записи конфигурации Xray")
        raise e


def reload_xray():
    """Перезагружает Xray для применения изменений."""
    try:
        # Используем restart вместо reload, так как Xray не поддерживает reload
        result = subprocess.run(
            ['systemctl', 'restart', 'xray'],
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        # Даем время на перезапуск
        time.sleep(2)
        
        # Проверяем, что сервис запущен
        check_result = subprocess.run(
            ['systemctl', 'is-active', 'xray'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if check_result.returncode == 0 and check_result.stdout.strip() == 'active':
            return True
        else:
            logging.warning("Xray может быть не запущен после перезагрузки")
            return False
    except subprocess.CalledProcessError as e:
        logging.error("Ошибка перезагрузки Xray: %s", e)
        if e.stderr:
            logging.error("Детали ошибки: %s", e.stderr)
        return False
    except subprocess.TimeoutExpired:
        logging.error("Таймаут при перезагрузке Xray")
        return False
    except Exception as e:
        logging.exception("Неожиданная ошибка при перезагрузке Xray: %s", e)
        return False


def get_or_create_xray_config() -> Dict:
    """Получает или создает базовую конфигурацию Xray."""
    config = read_xray_config()
    
    if not config:
        # Создаем базовую конфигурацию Xray
        config = {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                {
                    "port": settings.VPN_SERVER_PORT,
                    "protocol": "vless",
                    "settings": {
                        "clients": [],
                        "decryption": "none",
                        "fallbacks": []
                    },
                    "streamSettings": {
                        "network": "tcp",
                        "security": "reality",
                        "realitySettings": {
                            "show": False,
                            "dest": f"{settings.REALITY_SERVER_NAME}:443",
                            "serverNames": [
                                settings.REALITY_SERVER_NAME,
                                f"www.{settings.REALITY_SERVER_NAME}"
                            ],
                            "privateKey": settings.REALITY_PRIVATE_KEY,
                            "shortIds": [
                                settings.REALITY_SHORT_ID
                            ]
                        },
                        "tcpSettings": {}
                    },
                    "sniffing": {
                        "enabled": True,
                        "destOverride": ["http", "tls"]
                    }
                }
            ],
            "outbounds": [
                {
                    "protocol": "freedom",
                    "settings": {}
                },
                {
                    "protocol": "blackhole",
                    "settings": {},
                    "tag": "blocked"
                }
            ],
            "routing": {
                "rules": [
                    {
                        "type": "field",
                        "ip": ["geoip:private"],
                        "outboundTag": "blocked"
                    }
                ]
            }
        }
        write_xray_config(config)
    
    return config


def add_user_to_xray(uuid_str: str, email: str, reload_on_change: bool = True) -> bool:
    """Добавляет пользователя в конфигурацию Xray."""
    config = get_or_create_xray_config()
    
    # Проверяем, существует ли пользователь
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    # Проверяем по UUID
    for client in clients:
        if client.get("id") == uuid_str:
            logging.info("Пользователь с UUID %s уже существует в Xray", uuid_str)
            return True
    
    # Проверяем на дубликаты email и удаляем их (может быть только один пользователь с конкретным email)
    # Но оставляем пользователя с нужным UUID, если он есть
    clients_cleaned = []
    uuid_found = False
    
    for client in clients:
        client_uuid = client.get("id")
        client_email = client.get("email")
        
        # Если это наш пользователь - добавляем его
        if client_uuid == uuid_str:
            uuid_found = True
            clients_cleaned.append(client)
        # Если это другой пользователь с таким же email - пропускаем (дубликат)
        elif client_email == email:
            logging.warning("Найден дубликат email %s (UUID %s). Удаляем дубликат.", email, client_uuid)
            continue
        # Остальных добавляем
        else:
            clients_cleaned.append(client)
    
    # Если пользователя с нужным UUID не нашли - добавляем нового
    if not uuid_found:
        new_client = {
            "id": uuid_str,
            "email": email,
            "flow": ""  # Можно использовать "xtls-rprx-vision" для XTLS
        }
        clients_cleaned.append(new_client)
    
    config["inbounds"][0]["settings"]["clients"] = clients_cleaned
    
    write_xray_config(config)
    
    # Перезагружаем Xray, если требуется
    if reload_on_change:
        if reload_xray():
            logging.info("Пользователь %s добавлен в Xray и сервис перезагружен", email)
            return True
        else:
            logging.error("Ошибка при перезагрузке Xray после добавления пользователя %s", email)
            return False
    else:
        logging.info("Пользователь %s добавлен в Xray (перезагрузка отложена)", email)
        return True


def remove_user_from_xray(uuid_str: str) -> bool:
    """Удаляет пользователя из конфигурации Xray."""
    config = get_or_create_xray_config()
    
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    # Проверяем, что пользователь действительно существует
    user_exists = any(client.get("id") == uuid_str for client in clients)
    
    if not user_exists:
        logging.info("Пользователь с UUID %s не найден в Xray конфигурации", uuid_str)
        return True  # Уже удален - считаем успехом
    
    # Удаляем пользователя
    config["inbounds"][0]["settings"]["clients"] = [
        client for client in clients if client.get("id") != uuid_str
    ]
    
    # Сохраняем конфигурацию
    try:
        write_xray_config(config)
        logging.info("Пользователь с UUID %s удален из конфигурации Xray", uuid_str)
    except Exception as e:
        logging.exception("Ошибка при сохранении конфигурации Xray: %s", e)
        return False
    
    # Перезагружаем Xray
    if reload_xray():
        logging.info("Пользователь с UUID %s удален из Xray и сервис перезагружен", uuid_str)
        return True
    else:
        logging.error("Ошибка при перезагрузке Xray после удаления пользователя %s", uuid_str)
        # Даже если перезагрузка не удалась, конфигурация уже изменена
        # Возможно, нужно будет перезагрузить вручную
        return False


def check_xray_service_status() -> tuple[str, str]:
    """Проверяет статус Xray сервиса."""
    try:
        result = subprocess.run(
            ['systemctl', 'is-active', 'xray'],
            capture_output=True,
            text=True,
            timeout=3
        )
        status = result.stdout.strip()
        return status, ""
    except Exception as e:
        return "unknown", str(e)


def validate_xray_config() -> tuple[bool, str]:
    """Проверяет валидность конфигурации Xray."""
    try:
        candidates = [
            ['/usr/local/bin/xray', '-test', '-config', XRAY_CONFIG_PATH],
            ['xray', '-test', '-config', XRAY_CONFIG_PATH],
        ]
        last_error = ""
        for cmd in candidates:
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return True, ""
                else:
                    last_error = result.stderr or result.stdout
            except FileNotFoundError as e:
                last_error = str(e)
                continue
        return False, last_error
    except Exception as e:
        return False, str(e)


def fix_xray_config_duplicates() -> bool:
    """Исправляет дубликаты email в конфигурации Xray."""
    config = get_or_create_xray_config()
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    # Удаляем дубликаты - оставляем только уникальные email
    seen_emails = {}
    seen_uuids = set()
    clients_cleaned = []
    duplicates_removed = 0
    
    for client in clients:
        uuid_str = client.get('id')
        email = client.get('email')
        
        # Пропускаем если UUID уже есть
        if uuid_str in seen_uuids:
            duplicates_removed += 1
            continue
        
        # Если email уже есть - заменяем старую запись на новую (оставляем более позднюю)
        if email and email in seen_emails:
            old_uuid = seen_emails[email]
            # Удаляем старую запись
            clients_cleaned = [c for c in clients_cleaned if c.get('id') != old_uuid]
            # Добавляем новую
            clients_cleaned.append(client)
            seen_emails[email] = uuid_str
            duplicates_removed += 1
        else:
            clients_cleaned.append(client)
            if email:
                seen_emails[email] = uuid_str
        
        seen_uuids.add(uuid_str)
    
    if duplicates_removed > 0:
        config["inbounds"][0]["settings"]["clients"] = clients_cleaned
        write_xray_config(config)
        logging.info("Исправлено дубликатов: %d", duplicates_removed)
        return True
    
    return False


def check_and_fix_xray() -> dict:
    """
    Проверяет и исправляет проблемы с Xray.
    
    Returns:
        dict: Результаты проверки и исправления
    """
    results = {
        "config_duplicates_fixed": False,
        "service_restarted": False,
        "config_validated": False,
        "issues_found": []
    }
    
    logging.info("%s", "=" * 60)
    logging.info("Проверка и исправление проблем Xray")
    logging.info("%s", "=" * 60)
    
    # 1. Проверка и исправление дубликатов в конфигурации
    logging.info("1. Проверка дубликатов в конфигурации...")
    if fix_xray_config_duplicates():
        results["config_duplicates_fixed"] = True
        results["issues_found"].append("Обнаружены и исправлены дубликаты email в конфигурации")
        logging.info("   ✓ Дубликаты исправлены")
    else:
        logging.info("   ✓ Дубликатов не обнаружено")
    
    # 2. Валидация конфигурации
    logging.info("2. Валидация конфигурации Xray...")
    is_valid, error = validate_xray_config()
    if is_valid:
        results["config_validated"] = True
        logging.info("   ✓ Конфигурация валидна")
    else:
        results["issues_found"].append(f"Конфигурация Xray невалидна: {error}")
        logging.error("   ✗ Конфигурация невалидна: %s", error)
    
    # 3. Проверка статуса сервиса
    logging.info("3. Проверка статуса сервиса Xray...")
    status, error = check_xray_service_status()
    logging.info("   Статус: %s", status)
    
    if status != "active":
        results["issues_found"].append(f"Сервис Xray не запущен (статус: {status})")
        logging.warning("   ⚠ Сервис не запущен, пытаемся запустить...")
        
        # Пытаемся запустить сервис
        try:
            subprocess.run(
                ['systemctl', 'start', 'xray'],
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            time.sleep(2)
            
            # Проверяем еще раз
            new_status, _ = check_xray_service_status()
            if new_status == "active":
                results["service_restarted"] = True
                logging.info("   ✓ Сервис успешно запущен")
            else:
                logging.error("   ✗ Не удалось запустить сервис (статус: %s)", new_status)
        except Exception as e:
            results["issues_found"].append(f"Ошибка при попытке запуска сервиса: {e}")
            logging.exception("   ✗ Ошибка при запуске: %s", e)
    else:
        logging.info("   ✓ Сервис активен")
    
    # 4. Если были исправления - перезагружаем Xray
    if results["config_duplicates_fixed"]:
        logging.info("4. Перезагрузка Xray после исправлений...")
        if reload_xray():
            logging.info("   ✓ Xray перезагружен")
        else:
            results["issues_found"].append("Не удалось перезагрузить Xray после исправлений")
            logging.error("   ✗ Ошибка при перезагрузке")
    
    logging.info("%s", "=" * 60)
    
    return results


def is_user_in_xray(uuid_str: str) -> bool:
    """Проверяет, существует ли пользователь в конфигурации Xray."""
    config = get_or_create_xray_config()
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    for client in clients:
        if client.get("id") == uuid_str:
            return True
    return False


def clear_all_users_from_xray(reload_on_change: bool = True) -> bool:
    """Удаляет всех пользователей (clients) из конфигурации Xray и при необходимости перезагружает сервис.

    Args:
        reload_on_change: Выполнить перезагрузку сервиса Xray после изменений.

    Returns:
        bool: True при успехе, False при ошибке (например, не удалось перезагрузить).
    """
    config = get_or_create_xray_config()
    try:
        # Гарантируем структуру inbounds[0].settings.clients
        if "inbounds" not in config or not config["inbounds"]:
            config["inbounds"] = [{"settings": {"clients": []}}]
        if "settings" not in config["inbounds"][0]:
            config["inbounds"][0]["settings"] = {"clients": []}
        config["inbounds"][0]["settings"]["clients"] = []

        write_xray_config(config)
        logging.info("Все профили (clients) удалены из конфигурации Xray")

        if reload_on_change:
            if reload_xray():
                logging.info("Xray перезагружен после удаления всех профилей")
                return True
            else:
                logging.error("Не удалось перезагрузить Xray после удаления всех профилей")
                return False
        return True
    except Exception as e:
        logging.exception("Ошибка при очистке профилей Xray: %s", e)
        return False

