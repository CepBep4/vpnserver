import json
import subprocess
import os
from typing import Dict
from app.core.config import settings


XRAY_CONFIG_PATH = settings.XRAY_CONFIG_PATH


def read_xray_config() -> Dict:
    """Читает конфигурацию Xray из файла."""
    try:
        with open(XRAY_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def write_xray_config(config: Dict):
    """Записывает конфигурацию Xray в файл."""
    # Создаем временный файл для атомарной записи
    temp_path = XRAY_CONFIG_PATH + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        # Атомарно перемещаем файл
        os.rename(temp_path, XRAY_CONFIG_PATH)
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
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
        import time
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
            print(f"Предупреждение: Xray может быть не запущен после перезагрузки")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Ошибка перезагрузки Xray: {e}")
        if e.stderr:
            print(f"Детали ошибки: {e.stderr}")
        return False
    except subprocess.TimeoutExpired:
        print(f"Таймаут при перезагрузке Xray")
        return False
    except Exception as e:
        print(f"Неожиданная ошибка при перезагрузке Xray: {e}")
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


def add_user_to_xray(uuid_str: str, email: str) -> bool:
    """Добавляет пользователя в конфигурацию Xray."""
    config = get_or_create_xray_config()
    
    # Проверяем, существует ли пользователь
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    # Проверяем по UUID
    for client in clients:
        if client.get("id") == uuid_str:
            print(f"Пользователь с UUID {uuid_str} уже существует в Xray")
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
            print(f"Предупреждение: найден дубликат пользователя с email {email}, UUID {client_uuid}. Удаляем дубликат.")
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
    
    # Перезагружаем Xray
    if reload_xray():
        print(f"Пользователь {email} добавлен в Xray и сервис перезагружен")
        return True
    else:
        print(f"Ошибка при перезагрузке Xray после добавления пользователя {email}")
        return False


def remove_user_from_xray(uuid_str: str) -> bool:
    """Удаляет пользователя из конфигурации Xray."""
    config = get_or_create_xray_config()
    
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    # Проверяем, что пользователь действительно существует
    user_exists = any(client.get("id") == uuid_str for client in clients)
    
    if not user_exists:
        print(f"Пользователь с UUID {uuid_str} не найден в Xray конфигурации")
        return True  # Уже удален - считаем успехом
    
    # Удаляем пользователя
    config["inbounds"][0]["settings"]["clients"] = [
        client for client in clients if client.get("id") != uuid_str
    ]
    
    # Сохраняем конфигурацию
    try:
        write_xray_config(config)
        print(f"Пользователь с UUID {uuid_str} удален из конфигурации Xray")
    except Exception as e:
        print(f"Ошибка при сохранении конфигурации Xray: {e}")
        return False
    
    # Перезагружаем Xray
    if reload_xray():
        print(f"Пользователь с UUID {uuid_str} удален из Xray и сервис перезагружен")
        return True
    else:
        print(f"Ошибка при перезагрузке Xray после удаления пользователя {uuid_str}")
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
        result = subprocess.run(
            ['/usr/local/bin/xray', '-test', '-config', XRAY_CONFIG_PATH],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, ""
        else:
            return False, result.stderr
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
        print(f"Исправлено дубликатов: {duplicates_removed}")
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
    
    print("=" * 60)
    print("Проверка и исправление проблем Xray")
    print("=" * 60)
    
    # 1. Проверка и исправление дубликатов в конфигурации
    print("1. Проверка дубликатов в конфигурации...")
    if fix_xray_config_duplicates():
        results["config_duplicates_fixed"] = True
        results["issues_found"].append("Обнаружены и исправлены дубликаты email в конфигурации")
        print("   ✓ Дубликаты исправлены")
    else:
        print("   ✓ Дубликатов не обнаружено")
    
    # 2. Валидация конфигурации
    print("2. Валидация конфигурации Xray...")
    is_valid, error = validate_xray_config()
    if is_valid:
        results["config_validated"] = True
        print("   ✓ Конфигурация валидна")
    else:
        results["issues_found"].append(f"Конфигурация Xray невалидна: {error}")
        print(f"   ✗ Конфигурация невалидна: {error}")
    
    # 3. Проверка статуса сервиса
    print("3. Проверка статуса сервиса Xray...")
    status, error = check_xray_service_status()
    print(f"   Статус: {status}")
    
    if status != "active":
        results["issues_found"].append(f"Сервис Xray не запущен (статус: {status})")
        print(f"   ⚠ Сервис не запущен, пытаемся запустить...")
        
        # Пытаемся запустить сервис
        try:
            subprocess.run(
                ['systemctl', 'start', 'xray'],
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            import time
            time.sleep(2)
            
            # Проверяем еще раз
            new_status, _ = check_xray_service_status()
            if new_status == "active":
                results["service_restarted"] = True
                print("   ✓ Сервис успешно запущен")
            else:
                print(f"   ✗ Не удалось запустить сервис (статус: {new_status})")
        except Exception as e:
            results["issues_found"].append(f"Ошибка при попытке запуска сервиса: {e}")
            print(f"   ✗ Ошибка при запуске: {e}")
    else:
        print("   ✓ Сервис активен")
    
    # 4. Если были исправления - перезагружаем Xray
    if results["config_duplicates_fixed"]:
        print("4. Перезагрузка Xray после исправлений...")
        if reload_xray():
            print("   ✓ Xray перезагружен")
        else:
            results["issues_found"].append("Не удалось перезагрузить Xray после исправлений")
            print("   ✗ Ошибка при перезагрузке")
    
    print("=" * 60)
    
    return results


def is_user_in_xray(uuid_str: str) -> bool:
    """Проверяет, существует ли пользователь в конфигурации Xray."""
    config = get_or_create_xray_config()
    clients = config.get("inbounds", [{}])[0].get("settings", {}).get("clients", [])
    
    for client in clients:
        if client.get("id") == uuid_str:
            return True
    return False

