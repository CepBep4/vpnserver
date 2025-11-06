"""
Точка входа для запуска всех сервисов приложения.
Запускает FastAPI сервер, Celery Worker и Celery Beat вместе.
"""
import multiprocessing
import subprocess
import sys
import signal
import time
import os


def check_redis():
    """Проверяет доступность Redis."""
    import redis
    import os
    
    # Проверяем переменные окружения для Docker
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    
    try:
        r = redis.Redis(host=redis_host, port=redis_port, db=0, socket_timeout=2)
        r.ping()
        print(f"✓ Redis доступен на {redis_host}:{redis_port}")
        return True
    except Exception as e:
        print(f"✗ Redis недоступен на {redis_host}:{redis_port}: {e}")
        print("Попытка запустить Redis локально...")
        return False


def start_redis():
    """Пытается запустить Redis."""
    try:
        # Проверяем, можем ли мы запустить redis-server
        result = subprocess.run(
            ["redis-server", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("Запуск Redis сервера...")
            redis_process = subprocess.Popen(
                ["redis-server", "--daemonize", "yes"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            time.sleep(2)  # Даем время на запуск
            if check_redis():
                return redis_process
    except FileNotFoundError:
        print("Redis не установлен. Установите его командой:")
        print("  sudo apt-get install redis-server")
    except Exception as e:
        print(f"Ошибка при запуске Redis: {e}")
    return None


def run_fastapi():
    """Запускает FastAPI сервер."""
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Отключаем reload для запуска в процессе
        log_level="info"
    )


def run_celery_worker():
    """Запускает Celery Worker."""
    import sys
    sys.argv = ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
    from celery.__main__ import main
    main()


def run_celery_beat():
    """Запускает Celery Beat."""
    import sys
    sys.argv = ["celery", "-A", "app.celery_app", "beat", "--loglevel=info"]
    from celery.__main__ import main
    main()


def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения."""
    print("\nПолучен сигнал завершения. Остановка всех процессов...")
    sys.exit(0)


if __name__ == "__main__":
    # Настройка multiprocessing для Unix систем (fork для Linux)
    try:
        multiprocessing.set_start_method('fork', force=True)
    except RuntimeError:
        # Если уже установлен метод, используем его
        pass
    
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("VPN Server - Запуск всех сервисов")
    print("=" * 60)
    
    # Проверяем Redis
    redis_process = None
    redis_host = os.getenv('REDIS_HOST', 'localhost')
    redis_port = int(os.getenv('REDIS_PORT', '6379'))
    
    if not check_redis():
        # Пытаемся запустить Redis только если он не был указан через переменные окружения
        if redis_host == 'localhost':
            redis_process = start_redis()
            if not redis_process and not check_redis():
                print("\n⚠️  ВНИМАНИЕ: Redis недоступен!")
                print("Celery не сможет работать без Redis.")
                print("Установите Redis: sudo apt-get install redis-server")
                print("Или запустите через Docker: docker run -d -p 6379:6379 redis:latest")
                print("Или укажите REDIS_HOST и REDIS_PORT через переменные окружения")
                print("\nПродолжаю запуск только FastAPI сервера...")
                run_fastapi()
                sys.exit(0)
        else:
            print(f"\n⚠️  ВНИМАНИЕ: Redis недоступен на {redis_host}:{redis_port}!")
            print("Убедитесь, что Redis сервис запущен и доступен.")
            print("Продолжаю запуск только FastAPI сервера...")
            run_fastapi()
            sys.exit(0)
    
    print("\nЗапуск всех компонентов...")
    print("-" * 60)
    
    # Создаем процессы для каждого сервиса
    fastapi_process = multiprocessing.Process(target=run_fastapi, name="FastAPI")
    worker_process = multiprocessing.Process(target=run_celery_worker, name="CeleryWorker")
    beat_process = multiprocessing.Process(target=run_celery_beat, name="CeleryBeat")
    
    try:
        # Запускаем все процессы
        fastapi_process.start()
        print("✓ FastAPI сервер запущен на http://0.0.0.0:8000")
        
        worker_process.start()
        print("✓ Celery Worker запущен")
        
        beat_process.start()
        print("✓ Celery Beat запущен")
        
        print("-" * 60)
        print("Все сервисы запущены успешно!")
        print("Документация API: http://localhost:8000/docs")
        print("Для остановки нажмите Ctrl+C")
        print("-" * 60)
        
        # Ждем завершения всех процессов
        fastapi_process.join()
        worker_process.join()
        beat_process.join()
        
    except KeyboardInterrupt:
        print("\nОстановка всех процессов...")
        fastapi_process.terminate()
        worker_process.terminate()
        beat_process.terminate()
        
        # Ждем завершения
        fastapi_process.join(timeout=5)
        worker_process.join(timeout=5)
        beat_process.join(timeout=5)
        
        # Принудительно завершаем если не завершились
        if fastapi_process.is_alive():
            fastapi_process.kill()
        if worker_process.is_alive():
            worker_process.kill()
        if beat_process.is_alive():
            beat_process.kill()
        
        if redis_process:
            redis_process.terminate()
        
        print("Все процессы остановлены.")
