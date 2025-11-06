from app.celery_app import celery_app
from app.db.database import SessionLocal
from app.models.subscription import Subscription
from app.services.vless import create_vless_profile, disable_vless_profile, extract_uuid_from_link
from app.services.xray_manager import is_user_in_xray, add_user_to_xray, check_and_fix_xray, reload_xray
from datetime import datetime


@celery_app.task(name="app.tasks.subscription.check_subscriptions")
def check_subscriptions():
    """
    Периодическая задача для проверки подписок в БД.
    Выполняется каждую минуту.
    
    Логика:
    - Проверяет и исправляет проблемы с Xray
    - Если link пустое - генерируем и сохраняем ссылку (новый пользователь)
    - Если active=True и есть link - создаем/активируем VLESS профиль на VPN сервере
    - Если active=False - отключаем VLESS профиль на VPN сервере
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 60)
    print(f"[{timestamp}] Начало обхода базы данных подписок")
    print("=" * 60)
    
    # Проверяем и исправляем проблемы с Xray в начале обхода
    xray_check_results = check_and_fix_xray()
    print()
    
    db = SessionLocal()
    stats = {
        "total": 0,
        "new_links": 0,
        "activated": 0,
        "deactivated": 0,
        "no_changes": 0
    }
    
    try:
        reload_needed = False
        # Получаем все подписки
        subscriptions = db.query(Subscription).all()
        stats["total"] = len(subscriptions)
        
        print(f"[{timestamp}] Найдено подписок в базе: {stats['total']}")
        print("-" * 60)
        
        for subscription in subscriptions:
            print(f"[{timestamp}] Обработка пользователя: {subscription.username} (ID: {subscription.id})")
            print(f"  Статус: active={subscription.active}, link={'есть' if subscription.link else 'пусто'}")
            
            # Сначала обрабатываем активность пользователя - это приоритетнее
            # Если подписка активна и есть ссылка - создаем/активируем VLESS профиль на VPN сервере
            if subscription.active and subscription.link:
                print(f"  → Действие: Пользователь активен, проверяем и активируем VLESS профиль на VPN сервере (Reality)")
                # Убеждаемся, что пользователь добавлен в Xray
                uuid_from_link = extract_uuid_from_link(subscription.link)
                if uuid_from_link:
                    if not is_user_in_xray(uuid_from_link):
                        email = f"{subscription.username}@sunstrikevpn.local"
                        if add_user_to_xray(uuid_from_link, email, reload_on_change=False):
                            print(f"  ✓ Пользователь {subscription.username} добавлен в Xray")
                            reload_needed = True
                        else:
                            print(f"  ✗ Ошибка: не удалось добавить пользователя {subscription.username} в Xray")
                            stats["no_changes"] += 1
                            continue
                    else:
                        print(f"  ✓ Пользователь {subscription.username} уже активен в Xray")
                    stats["activated"] += 1
                else:
                    print(f"  ✗ Ошибка: не удалось извлечь UUID из ссылки")
                    stats["no_changes"] += 1
            
            # Если подписка неактивна, но есть ссылка - отключаем VLESS профиль на VPN сервере
            elif not subscription.active and subscription.link:
                print(f"  → Действие: Обнаружена неактивная подписка, отключаем профиль на VPN сервере")
                
                # Отключаем VLESS профиль на VPN сервере
                disable_vless_profile(subscription)
                
                # Ссылку оставляем в БД (не удаляем)
                print(f"  ✓ Отключен VLESS профиль для {subscription.username}")
                stats["deactivated"] += 1
            
            # Если ссылка пустая - значит пользователь новый, создаем ссылку
            if not subscription.link:
                print(f"  → Действие: Обнаружен новый пользователь (нет ссылки)")
                
                # Генерируем и сохраняем VLESS ссылку с Reality
                link, uuid = create_vless_profile(subscription)
                subscription.link = link
                db.commit()
                
                print(f"  ✓ Сгенерирована и сохранена Reality ссылка для {subscription.username}")
                print(f"    UUID: {uuid}")
                stats["new_links"] += 1
            
            # Если ссылка есть, но не в формате Reality - обновляем её
            elif subscription.link and "security=reality" not in subscription.link:
                print(f"  → Действие: Обнаружена старая ссылка (не Reality), обновляем на Reality формат")
                
                # Обновляем ссылку на формат Reality
                link, uuid = create_vless_profile(subscription)
                subscription.link = link
                db.commit()
                
                print(f"  ✓ Ссылка обновлена на Reality формат для {subscription.username}")
                stats["new_links"] += 1
            
            # Проверяем, соответствует ли имя в ссылке текущему VPN_NAME из конфига
            elif subscription.link:
                from app.core.config import settings
                import urllib.parse
                
                # Извлекаем имя из текущей ссылки
                if '#' in subscription.link:
                    current_remark_encoded = subscription.link.split('#')[-1]
                    current_remark = urllib.parse.unquote(current_remark_encoded)
                    
                    # Сравниваем с текущим VPN_NAME
                    if current_remark != settings.VPN_NAME:
                        print(f"  → Действие: Имя в ссылке не соответствует VPN_NAME из конфига, обновляем")
                        print(f"    Старое имя: {current_remark}")
                        print(f"    Новое имя: {settings.VPN_NAME}")
                        
                        # Генерируем новую ссылку с правильным именем
                        uuid_from_link = extract_uuid_from_link(subscription.link)
                        if uuid_from_link:
                            from app.services.vless import generate_vless_link_only
                            new_link = generate_vless_link_only(uuid_from_link)
                            subscription.link = new_link
                            db.commit()
                            print(f"  ✓ Ссылка обновлена с правильным именем для {subscription.username}")
                            stats["new_links"] += 1
                        else:
                            print(f"  ✗ Ошибка: не удалось извлечь UUID для обновления ссылки")
            
            # Если подписка неактивна и нет ссылки - ничего не делаем
            elif not subscription.active and not subscription.link:
                print(f"  → Действие: Пользователь неактивен и нет ссылки - пропускаем")
                stats["no_changes"] += 1
            
            print()
        
        print("-" * 60)
        print(f"[{timestamp}] Обход завершен. Статистика:")
        print(f"  Всего подписок: {stats['total']}")
        print(f"  Создано новых ссылок: {stats['new_links']}")
        print(f"  Активировано профилей: {stats['activated']}")
        print(f"  Отключено профилей: {stats['deactivated']}")
        print(f"  Без изменений: {stats['no_changes']}")

        # Единоразовая перезагрузка Xray, если в ходе обхода были изменения
        if reload_needed:
            print("Перезагрузка Xray после изменений пользователей...")
            if reload_xray():
                print("  ✓ Xray перезагружен")
            else:
                print("  ✗ Не удалось перезагрузить Xray. Проверьте состояние сервиса.")
        
        # Показываем результаты проверки Xray
        if xray_check_results.get("issues_found"):
            print()
            print("Обнаруженные проблемы Xray:")
            for issue in xray_check_results["issues_found"]:
                print(f"  ⚠ {issue}")
        elif xray_check_results.get("config_duplicates_fixed"):
            print()
            print("  ✓ Проблемы Xray исправлены")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"[{timestamp}] ✗ ОШИБКА при проверке подписок: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
        print(f"[{timestamp}] Соединение с базой данных закрыто\n")
