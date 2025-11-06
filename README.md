# VPN Server API

FastAPI сервис с SQLite3 базой данных, Celery для фоновых задач и поддержкой VLESS VPN.

## Требования

- Python 3.8+
- Redis (для Celery брокера)

## Установка зависимостей

```bash
# Активация виртуального окружения
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Установка и запуск Redis (если еще не установлен)
# Ubuntu/Debian:
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis

# Или используйте Docker:
docker run -d -p 6379:6379 redis:latest
```

## Запуск сервиса

### 1. Запуск FastAPI сервера

```bash
# Активация виртуального окружения
source .venv/bin/activate

# Запуск через uvicorn
python main.py

# Или напрямую через uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Запуск Celery Worker

В отдельном терминале:

```bash
source .venv/bin/activate

# Запуск worker
python celery_worker.py

# Или напрямую через celery
celery -A app.celery_app worker --loglevel=info
```

### 3. Запуск Celery Beat (планировщик задач)

В отдельном терминале:

```bash
source .venv/bin/activate

# Запуск beat
python celery_beat.py

# Или напрямую через celery
celery -A app.celery_app beat --loglevel=info
```

### Запуск всех компонентов вместе

Для удобства можно использовать tmux или screen:

```bash
# tmux пример
tmux new-session -d -s vpnserver
tmux new-window -t vpnserver:1 -n api
tmux new-window -t vpnserver:2 -n worker
tmux new-window -t vpnserver:3 -n beat

tmux send-keys -t vpnserver:api "source .venv/bin/activate && python main.py" Enter
tmux send-keys -t vpnserver:worker "source .venv/bin/activate && python celery_worker.py" Enter
tmux send-keys -t vpnserver:beat "source .venv/bin/activate && python celery_beat.py" Enter

tmux attach -t vpnserver
```

## API Документация

После запуска сервера доступна документация:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI схема: http://localhost:8000/openapi.json

## Эндпоинты

### Base группа

- `GET /health` - Проверка здоровья сервиса (без аутентификации)
- `GET /protected` - Пример защищенного эндпоинта (требует JWT токен)

### Authentication группа

- `POST /auth/login` - Авторизация и получение JWT токена (без аутентификации)

## Аутентификация

API использует JWT (JSON Web Tokens) для защиты эндпоинтов.

### Получение токена

1. Отправьте POST запрос на `/auth/login` с HTTP Basic Auth:
   ```bash
   curl -X POST "http://localhost:8000/auth/login" \
     -u admin:admin \
     -H "accept: application/json"
   ```

2. Ответ будет содержать токен:
   ```json
   {
     "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     "token_type": "bearer"
   }
   ```

### Использование токена

Используйте токен в заголовке `Authorization` для защищенных эндпоинтов:
```bash
curl -X GET "http://localhost:8000/protected" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "accept: application/json"
```

### Настройка учетных данных

Учетные данные администратора и настройки JWT хранятся в конфигурации (`app/core/config.py`):

- `ADMIN_USERNAME` - логин администратора (по умолчанию: `admin`)
- `ADMIN_PASSWORD` - пароль администратора (по умолчанию: `admin`)
- `SECRET_KEY` - секретный ключ для подписи JWT токенов
- `ACCESS_TOKEN_EXPIRE_MINUTES` - время жизни токена в минутах (по умолчанию: 30)

Вы можете переопределить эти значения через переменные окружения или создать файл `.env`:

```env
ADMIN_USERNAME=your_username
ADMIN_PASSWORD=your_password
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

### Swagger UI

В Swagger UI доступна встроенная авторизация:
1. Откройте http://localhost:8000/docs
2. Нажмите кнопку "Authorize" 
3. Введите логин и пароль в поле Basic Auth
4. Получите токен через `/auth/login`
5. Используйте полученный токен в поле Bearer для защищенных эндпоинтов

## Структура проекта

```
vpnserver/
├── app/
│   ├── __init__.py
│   ├── main.py              # Основное приложение FastAPI
│   ├── celery_app.py        # Конфигурация Celery
│   ├── api/
│   │   ├── __init__.py
│   │   ├── base.py          # Эндпоинты группы base
│   │   └── auth.py           # Эндпоинты аутентификации
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py        # Настройки приложения
│   │   └── security.py       # JWT и безопасность
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py      # Настройка базы данных
│   ├── models/
│   │   ├── __init__.py
│   │   └── subscription.py  # Модель подписок
│   ├── services/
│   │   ├── __init__.py
│   │   └── vless.py         # Сервис для работы с VLESS
│   └── tasks/
│       ├── __init__.py
│       └── subscription.py  # Celery задачи для подписок
├── main.py                  # Точка входа для запуска API
├── celery_worker.py         # Скрипт запуска Celery Worker
├── celery_beat.py           # Скрипт запуска Celery Beat
├── requirements.txt         # Зависимости проекта
└── README.md
```

## Как работает система

1. **FastAPI сервер** - основной API сервер для управления подписками
2. **Celery Worker** - обрабатывает фоновые задачи
3. **Celery Beat** - запускает периодические задачи каждую минуту

### Автоматическая обработка подписок

Каждую минуту Celery Beat запускает задачу `check_subscriptions`, которая:

- **Проверяет новые активные подписки** (`active=True` и нет `link`):
  - Создает VLESS профиль
  - Генерирует уникальную VLESS ссылку
  - Сохраняет ссылку в базе данных

- **Проверяет неактивные подписки** (`active=False` и есть `link`):
  - Отключает VLESS профиль на VPN сервере
  - Оставляет ссылку в БД (не удаляет)

## База данных

SQLite база данных создается автоматически в файле `vpnserver.db` при первом запуске.

### Таблица `subscriptions`

- `id` - первичный ключ
- `username` - уникальное имя пользователя (может быть числом)
- `password` - пароль
- `active` - булево поле (активна ли подписка)
- `link` - VLESS ссылка (генерируется автоматически)

## Конфигурация VLESS

Настройки VLESS сервера находятся в `app/services/vless.py`:

```python
VLESS_SERVER_HOST = "your-server.com"  # Замените на ваш сервер
VLESS_SERVER_PORT = 443                # Порт сервера
```

## Примечания

- Перед тестированием убедитесь, что Redis запущен
- Для продакшена рекомендуется использовать Supervisor или systemd для управления процессами
- VLESS профили пока не создаются на реальном VPN сервере - это нужно будет реализовать позже


