#!/bin/bash
set -e

echo "=========================================="
echo "VPN Server - Docker Container Startup"
echo "=========================================="

# Проверяем наличие CONF.py
if [ ! -f "/app/CONF.py" ]; then
    echo "⚠️  ВНИМАНИЕ: CONF.py не найден!"
    echo "Создайте файл CONF.py с необходимыми настройками."
    exit 1
fi

# Проверяем наличие Xray бинарника
if [ ! -f "/usr/local/bin/xray" ]; then
    echo "⚠️  ВНИМАНИЕ: Xray не найден!"
    exit 1
fi

# Проверяем версию Xray
echo "Проверка Xray..."
/usr/local/bin/xray -version || true

# Создаем начальную конфигурацию Xray если её нет
if [ ! -f "/usr/local/etc/xray/config.json" ]; then
    echo "Создание начальной конфигурации Xray..."
    mkdir -p /usr/local/etc/xray
    # Конфигурация будет создана автоматически при первом запуске через Python
fi

# Проверяем Redis перед запуском
echo "Проверка Redis..."
if [ -z "$REDIS_HOST" ]; then
    REDIS_HOST="redis"
fi
if [ -z "$REDIS_PORT" ]; then
    REDIS_PORT="6379"
fi

# Ждем доступности Redis
for i in {1..30}; do
    if python3 -c "import redis; r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, db=0, socket_timeout=2); r.ping()" 2>/dev/null; then
        echo "✓ Redis доступен на $REDIS_HOST:$REDIS_PORT"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "⚠️  ВНИМАНИЕ: Redis недоступен после 30 попыток!"
        echo "Продолжаю запуск без Redis (Celery не будет работать)..."
    else
        echo "Ожидание Redis... ($i/30)"
        sleep 1
    fi
done

# Обновляем переменные окружения для Celery
export CELERY_BROKER_URL=${CELERY_BROKER_URL:-"redis://${REDIS_HOST}:${REDIS_PORT}/0"}
export CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-"redis://${REDIS_HOST}:${REDIS_PORT}/0"}

# Запускаем приложение
echo "=========================================="
echo "Запуск VPN Server..."
echo "=========================================="

# Если указан режим только API (без Celery)
if [ "$API_ONLY" = "true" ]; then
    echo "Запуск только FastAPI сервера..."
    exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
else
    # Запускаем все сервисы вместе
    exec python3 main.py
fi

