# VPN Server - Docker Deployment Guide

## Описание

Docker контейнер для VPN сервера на базе FastAPI, Xray-core, Celery и Redis. Позволяет быстро развернуть весь стек приложения на новом сервере.

## Требования

- Docker Engine 20.10+
- Docker Compose 2.0+
- Минимум 1GB RAM
- Минимум 2GB свободного места на диске

## Быстрый старт

### 1. Клонирование или копирование проекта

```bash
# Если у вас уже есть проект
cd /path/to/vpnserver

# Убедитесь, что файл CONF.py существует и настроен правильно
ls -la CONF.py
```

### 2. Настройка CONF.py

Отредактируйте файл `CONF.py` и укажите все необходимые параметры:

```python
# Учетные данные администратора
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "ваш_пароль"

# Секретный ключ для JWT (сгенерируйте новый!)
SECRET_KEY = "ваш_секретный_ключ"

# Настройки VPN сервера
VPN_SERVER_HOST = "ваш_ip_адрес"
VPN_SERVER_PORT = 443

# Настройки Reality протокола
REALITY_PRIVATE_KEY = "ваш_приватный_ключ"
REALITY_PUBLIC_KEY = "ваш_публичный_ключ"
# ... и т.д.
```

### 3. Создание необходимых директорий

```bash
mkdir -p data xray-config logs
```

### 4. Запуск через Docker Compose

```bash
# Сборка и запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

### 5. Проверка работы

```bash
# Проверка здоровья API
curl http://localhost:8000/health

# Проверка метрик
curl http://localhost:8000/metrics

# Документация API
# Откройте в браузере: http://localhost:8000/docs
```

## Структура проекта

```
vpnserver/
├── app/                    # Код приложения
├── data/                   # Данные (SQLite БД, создается автоматически)
├── xray-config/            # Конфигурация Xray (создается автоматически)
├── logs/                   # Логи приложения
├── CONF.py                 # Конфигурация (обязательно!)
├── Dockerfile              # Docker образ приложения
├── docker-compose.yml      # Конфигурация Docker Compose
├── docker-entrypoint.sh    # Скрипт запуска контейнера
└── requirements.txt        # Python зависимости
```

## Переменные окружения

Переменные окружения можно указать в `docker-compose.yml` или через `.env` файл:

```bash
# Redis настройки
REDIS_HOST=redis          # Хост Redis (по умолчанию redis)
REDIS_PORT=6379           # Порт Redis (по умолчанию 6379)

# Celery настройки
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Режим работы (опционально)
API_ONLY=false            # Если true - запускается только FastAPI без Celery
```

## Порты

- **8000** - FastAPI API сервер
- **443** - Xray VPN сервер (VLESS)
- **6379** - Redis (внутренний, можно не публиковать)

## Volumes

Приложение использует следующие volumes для сохранения данных:

- `./data` - SQLite база данных и другие данные приложения
- `./xray-config` - Конфигурация Xray
- `./logs` - Логи приложения

## Управление

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Только приложение
docker-compose logs -f vpnserver

# Только Redis
docker-compose logs -f redis
```

### Перезапуск сервисов

```bash
# Перезапуск приложения
docker-compose restart vpnserver

# Перезапуск всех сервисов
docker-compose restart
```

### Обновление приложения

```bash
# Остановка
docker-compose down

# Пересборка образа
docker-compose build --no-cache

# Запуск
docker-compose up -d
```

### Очистка (удаление всех данных)

```bash
# Остановка и удаление контейнеров
docker-compose down

# Удаление volumes (ВНИМАНИЕ: удалит все данные!)
docker-compose down -v
```

## Развертывание на production сервере

### 1. Безопасность

- **Обязательно** измените пароль администратора в `CONF.py`
- **Обязательно** сгенерируйте новый `SECRET_KEY` для JWT
- Используйте сильные пароли для всех пользователей
- Рассмотрите использование reverse proxy (nginx) перед FastAPI
- Настройте firewall для ограничения доступа к портам

### 2. Обновление через Git

```bash
# Клонирование репозитория
git clone <repository-url>
cd vpnserver

# Создание CONF.py из примера
cp CONF.py.example CONF.py
# Редактирование CONF.py

# Запуск
docker-compose up -d
```

### 3. Systemd сервис (опционально)

Создайте файл `/etc/systemd/system/vpnserver.service`:

```ini
[Unit]
Description=VPN Server Docker Compose
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/path/to/vpnserver
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Затем:

```bash
sudo systemctl enable vpnserver
sudo systemctl start vpnserver
```

## Troubleshooting

### Проблема: Redis не доступен

```bash
# Проверьте статус Redis контейнера
docker-compose ps redis

# Проверьте логи Redis
docker-compose logs redis

# Перезапустите Redis
docker-compose restart redis
```

### Проблема: Xray не запускается

```bash
# Проверьте конфигурацию Xray
docker-compose exec vpnserver /usr/local/bin/xray -test -config /usr/local/etc/xray/config.json

# Проверьте логи
docker-compose logs vpnserver | grep -i xray

# Проверьте права доступа на конфигурацию
docker-compose exec vpnserver ls -la /usr/local/etc/xray/
```

### Проблема: Порт 443 уже занят

Если порт 443 занят другим приложением, измените маппинг портов в `docker-compose.yml`:

```yaml
ports:
  - "8000:8000"
  - "8443:443"  # Используйте другой внешний порт
```

И обновите `VPN_SERVER_PORT` в `CONF.py` соответственно.

### Проблема: База данных не сохраняется

Убедитесь, что volume `./data` создан и имеет правильные права:

```bash
mkdir -p data
chmod 755 data
```

## Версии

- **Python**: 3.12
- **Xray**: Последняя версия (автоматически загружается при сборке)
- **Redis**: 7.0-alpine
- **FastAPI**: 0.104.1
- **Celery**: 5.3.4

## Поддержка

При возникновении проблем проверьте логи:

```bash
docker-compose logs -f --tail=100
```

## Лицензия

[Укажите лицензию проекта]

