"""Тестовые фикстуры: токен до импорта сервера."""

import os

os.environ.setdefault("YOZHKA_ACCESS_TOKEN", "test-access")
os.environ.setdefault("YOZHKA_BASE_URL", "https://yozhka.lukit.ru/backend")
