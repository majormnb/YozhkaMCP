"""Конфигурация yozhka-mcp через переменные окружения / .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://yozhka.lukit.ru/backend"


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Загружается один раз при старте сервера из env / .env."""

    def __init__(self) -> None:
        # .env рядом с проектом — удобно для локального запуска
        load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
        load_dotenv()  # и из текущего каталога

        self.base_url: str = os.environ.get("YOZHKA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        # Основной способ: refresh-токен (живёт ~30 дней), access получаем сами.
        self.refresh_token: str | None = os.environ.get("YOZHKA_REFRESH_TOKEN") or None
        # Альтернатива: готовый access-токен (живёт ~1 час).
        self.access_token: str | None = os.environ.get("YOZHKA_ACCESS_TOKEN") or None
        self.read_only: bool = _env_bool("YOZHKA_READ_ONLY", default=False)
        self.request_timeout: float = float(os.environ.get("YOZHKA_TIMEOUT", "30"))
        self.max_retries: int = int(os.environ.get("YOZHKA_MAX_RETRIES", "3"))
        self.debug: bool = _env_bool("YOZHKA_DEBUG", default=False)

    @property
    def has_auth(self) -> bool:
        return bool(self.access_token or self.refresh_token)


config = Config()
