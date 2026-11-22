"""Кэш цепочки токенов на диске.

Один логин Ёжки может жить неограниченно долго: /auth/refresh отдаёт новый
refresh-токен, а старый при этом не инвалидируется (проверено живыми вызовами).
Храним новейшую пару на диске — и ручная добыча токена из браузера нужна ровно один раз.

Приоритет при загрузке: если YOZHKA_REFRESH_TOKEN в env не менялся с момента
последней записи кэша — берём кэш (цепочка ушла вперёд); если пользователь
положил в .env новый токен (fingerprint не совпал) — env выигрывает как новый bootstrap.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("yozhka_mcp")

# access-токен считаем годным, пока до exp больше этого запаса (сек, скос часов)
_EXPIRY_MARGIN = 60


def _fingerprint(token: str | None) -> str | None:
    if not token:
        return None
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def _jwt_exp(token: str | None) -> float | None:
    """exp из payload JWT без проверки подписи (свой токен, нам нужна только свежесть)."""
    if not token:
        return None
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0)) or None
    except Exception:  # noqa: BLE001 — битый токен не должен ломать загрузку
        return None


class TokenStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def load(self, env_refresh: str | None, env_access: str | None) -> tuple[str | None, str | None]:
        """→ (refresh_token, access_token)."""
        try:
            cache = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return env_refresh, env_access
        if not isinstance(cache, dict):
            return env_refresh, env_access

        if env_refresh and _fingerprint(env_refresh) != cache.get("fingerprint"):
            return env_refresh, env_access  # в .env положили новый токен — он главнее

        refresh = cache.get("refreshToken") or env_refresh
        access = env_access  # явный YOZHKA_ACCESS_TOKEN — override (тесты/отладка)
        if not access:
            cached = cache.get("accessToken")
            if cached and (cache.get("accessExpiresAt") or 0) > time.time() + _EXPIRY_MARGIN:
                access = cached
        return refresh, access

    def save(self, refresh: str | None, access: str | None, env_refresh: str | None) -> None:
        data = {
            "refreshToken": refresh,
            "accessToken": access,
            "accessExpiresAt": _jwt_exp(access),
            "fingerprint": _fingerprint(env_refresh),
            "savedAt": time.time(),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, ensure_ascii=False))
            os.chmod(tmp, 0o600)
            os.replace(tmp, self.path)
        except OSError as exc:  # несмертельный кэш не должен ломать запросы
            logger.warning("token cache: не записан %s: %s", self.path, exc)
