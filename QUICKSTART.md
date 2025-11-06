# VPN Server - Быстрый старт с Docker

## Быстрая установка на новом сервере

### 1. Подготовка

```bash
# Клонируйте или скопируйте проект
cd /root/vpnserver

# Убедитесь, что CONF.py настроен правильно
nano CONF.py
```

**Важно:** Обязательно настройте в `CONF.py`:
- `ADMIN_USERNAME` и `ADMIN_PASSWORD` - учетные данные администратора
- `SECRET_KEY` - секретный ключ для JWT (сгенерируйте новый!)
- `VPN_SERVER_HOST` - IP адрес вашего сервера
- Все параметры Reality протокола

### 2. Запуск через Docker Compose

```bash
# Создайте необходимые директории
mkdir -p data xray-config logs

# Соберите и запустите контейнеры
docker-compose up -d --build

# Проверьте статус
docker-compose ps

# Просмотрите логи
docker-compose logs -f
```

### 3. Проверка работы

```bash
# Проверка здоровья API
curl http://localhost:8000/health

# Проверка метрик
curl http://localhost:8000/metrics

# Откройте документацию API в браузере
# http://ваш-ip:8000/docs
```

### 4. Проверка Xray

```bash
# Проверка статуса Xray внутри контейнера
docker-compose exec vpnserver /usr/local/bin/xray -version

# Проверка конфигурации Xray
docker-compose exec vpnserver /usr/local/bin/xray -test -config /usr/local/etc/xray/config.json
```

## Управление

```bash
# Остановка
docker-compose down

# Перезапуск
docker-compose restart

# Просмотр логов
docker-compose logs -f vpnserver

# Очистка (удаление всех данных!)
docker-compose down -v
```

## Структура данных

Все данные сохраняются в volumes:
- `./data` - база данных SQLite
- `./xray-config` - конфигурация Xray
- `./logs` - логи приложения

## Troubleshooting

### Проблема: Redis не доступен
```bash
docker-compose restart redis
docker-compose logs redis
```

### Проблема: Порт 443 занят
Измените маппинг портов в `docker-compose.yml`:
```yaml
ports:
  - "8000:8000"
  - "8443:443"  # Используйте другой порт
```

### Проблема: Xray не работает
Возможно, потребуется привилегированный режим. Раскомментируйте в `docker-compose.yml`:
```yaml
privileged: true
# или
network_mode: host
```

## Подробная документация

Смотрите [DOCKER.md](DOCKER.md) для полной документации.

