"""Тестовые фикстуры: окружение до импорта сервера."""

import os

os.environ.setdefault("YOZHKA_ACCESS_TOKEN", "test-access")
os.environ.setdefault("YOZHKA_BASE_URL", "https://yozhka.lukit.ru/backend")
# в .env разработчика может быть READ_ONLY=1 — тестам нужны write-тулы
os.environ.setdefault("YOZHKA_READ_ONLY", "0")
os.environ.setdefault("YOZHKA_TRANSPORT", "stdio")
