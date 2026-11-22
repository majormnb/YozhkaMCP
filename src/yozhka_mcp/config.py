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
        if not (self.base_url.startswith("https://")
                or self.base_url.startswith("http://localhost")
                or self.base_url.startswith("http://127.0.0.1")):
            # иначе свежий Bearer-токен уйдёт на произвольный хост
            raise ValueError(
                f"YOZHKA_BASE_URL должен быть https://… или http://localhost…, получено: {self.base_url!r}"
            )
        # Основной способ: refresh-токен. Ротация бесконечная: каждый refresh выдаёт
        # новый refresh-токен, он сохраняется в кеш-файл (права 0600) — одна сессия
        # живёт вечно, пока Ёжку дёргают чаще раза в месяц.
        self.refresh_token: str | None = os.environ.get("YOZHKA_REFRESH_TOKEN") or None
        # Альтернатива: готовый access-токен (живёт ~1 час).
        self.access_token: str | None = os.environ.get("YOZHKA_ACCESS_TOKEN") or None
        # Кеш цепочки токенов: "" / "off" отключает, иначе путь (по умолчанию — рядом с .env).
        default_cache = Path(__file__).resolve().parent.parent.parent / ".yozhka-token-cache.json"
        cache_env = os.environ.get("YOZHKA_TOKEN_CACHE", str(default_cache)).strip()
        self.token_cache_path: str | None = None if cache_env.lower() in {"", "off", "0", "none"} else cache_env
        self.read_only: bool = _env_bool("YOZHKA_READ_ONLY", default=False)
        self.request_timeout: float = float(os.environ.get("YOZHKA_TIMEOUT", "30"))
        self.max_retries: int = int(os.environ.get("YOZHKA_MAX_RETRIES", "3"))
        self.debug: bool = _env_bool("YOZHKA_DEBUG", default=False)
        # Транспорт: stdio (по умолчанию, для локальных клиентов) или http
        # (streamable-http, для запуска как сервиса — Docker/NAS/VPS).
        self.transport: str = os.environ.get("YOZHKA_TRANSPORT", "stdio").strip().lower()
        self.host: str = os.environ.get("YOZHKA_HOST", "127.0.0.1")
        self.port: int = int(os.environ.get("YOZHKA_PORT", "8000"))
        # http-режим: если задан, все запросы должны нести Authorization: Bearer <token>
        # или X-MCP-Token. Без токена эндпоинт доступен только с localhost.
        self.http_token: str | None = os.environ.get("YOZHKA_HTTP_TOKEN") or None
        # Лимит одновременных запросов к API: лишние ждут локально, не долбя сервер.
        self.max_concurrent: int = int(os.environ.get("YOZHKA_MAX_CONCURRENT", "4"))

    @property
    def has_auth(self) -> bool:
        return bool(self.access_token or self.refresh_token)


config = Config()
