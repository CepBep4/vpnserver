#!/usr/bin/env python
"""
Скрипт для запуска Celery Beat (планировщик задач).

Запуск:
    celery -A app.celery_app beat --loglevel=info
    или
    python celery_beat.py
"""
import sys
from celery.__main__ import main

if __name__ == "__main__":
    sys.argv = ["celery", "-A", "app.celery_app", "beat", "--loglevel=info"]
    main()

