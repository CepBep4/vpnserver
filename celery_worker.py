#!/usr/bin/env python
"""
Скрипт для запуска Celery Worker.

Запуск:
    celery -A app.celery_app worker --loglevel=info
    или
    python celery_worker.py
"""
import sys
from celery.__main__ import main

if __name__ == "__main__":
    sys.argv = ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
    main()

