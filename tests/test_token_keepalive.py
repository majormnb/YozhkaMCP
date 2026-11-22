"""Тесты вечного режима токенов и лимита параллельных запросов."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
import respx

from yozhka_mcp.api.client import YozhkaClient
from yozhka_mcp.api.token_store import TokenStore
from yozhka_mcp.config import Config

BASE = "https://yozhka.lukit.ru/backend"


def _fake_jwt(exp: float) -> str:
    """JWT-подобный токен с exp в payload (подпись фиктивная — она не проверяется)."""
    import base64
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=")
    return f"{enc({'alg': 'HS256'}).decode()}.{enc({'exp': exp}).decode()}.sig"


def _cfg(tmp_path, **kwargs) -> Config:
    cfg = Config.__new__(Config)
    cfg.base_url = BASE
    cfg.access_token = "test-access"
    cfg.refresh_token = "env-refresh"
    cfg.read_only = False
    cfg.request_timeout = 5.0
    cfg.max_retries = 3
    cfg.max_concurrent = 4
    cfg.debug = False
    cfg.token_cache_path = str(tmp_path / "cache.json")
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


# ---------- TokenStore ----------

def test_token_store_roundtrip(tmp_path):
    path = tmp_path / "cache.json"
    store = TokenStore(path)
    jwt = _fake_jwt(9_999_999_999)
    store.save("new-refresh", jwt, env_refresh="env-refresh")
    refresh, access = TokenStore(path).load("env-refresh", None)
    assert refresh == "new-refresh"
    assert access == jwt


def test_token_store_env_token_beats_stale_cache(tmp_path):
    """В .env положили НОВЫЙ bootstrap-токен — он главнее кеша."""
    path = tmp_path / "cache.json"
    TokenStore(path).save("cached-refresh", "cached-access", env_refresh="old-env")
    refresh, access = TokenStore(path).load("brand-new-env", None)
    assert refresh == "brand-new-env"
    assert access is None  # access из кеша чужого fingerprint не берём


def test_token_store_expired_access_ignored(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({
        "refreshToken": "r", "accessToken": "stale",
        "accessExpiresAt": 1, "fingerprint": None, "savedAt": 0}), encoding="utf-8")
    refresh, access = TokenStore(path).load("r", None)
    assert refresh == "r"
    assert access is None


def test_token_store_file_permissions_0600(tmp_path):
    import os
    path = tmp_path / "cache.json"
    TokenStore(path).save("r", "a", "r")
    assert (os.stat(path).st_mode & 0o777) == 0o600


def test_token_store_corrupt_file_falls_back_to_env(tmp_path):
    path = tmp_path / "cache.json"
    path.write_text("не-json", encoding="utf-8")
    refresh, access = TokenStore(path).load("env-refresh", None)
    assert (refresh, access) == ("env-refresh", None)


# ---------- вечный режим через клиент ----------

@respx.mock
async def test_refresh_persists_chain_and_next_client_skips_refresh(tmp_path):
    """Первый клиент делает refresh и сохраняет цепочку; второй стартует
    сразу с закешированного access — refresh-эндпоинт не дёргается."""
    cfg = _cfg(tmp_path, access_token=None)
    jwt = _fake_jwt(9_999_999_999)
    respx.post(f"{BASE}/auth/refresh").respond(
        json={"accessToken": jwt, "refreshToken": "refresh-1"})
    respx.get(f"{BASE}/userProfile").respond(json={"id": 1})

    c1 = YozhkaClient(cfg)
    await c1.get_my_profile()
    assert c1._refresh_token == "refresh-1"
    await c1.aclose()

    respx.post(f"{BASE}/auth/refresh").respond(json={"accessToken": "x", "refreshToken": "y"})
    c2 = YozhkaClient(cfg)  # поднимается уже с закешированной парой
    assert c2._access_token == jwt
    assert c2._refresh_token == "refresh-1"
    await c2.get_my_profile()
    refresh_calls = [r for r in respx.calls if r.request.url.path.endswith("/auth/refresh")]
    assert len(refresh_calls) == 1  # второй клиент refresh не дёргал
    await c2.aclose()


@respx.mock
async def test_concurrency_limited_to_max_concurrent(tmp_path):
    """8 параллельных вызовов: в полёте не больше cfg.max_concurrent."""
    in_flight = 0
    max_seen = 0

    async def counting_handler(request):
        nonlocal in_flight, max_seen
        in_flight += 1
        max_seen = max(max_seen, in_flight)
        await asyncio.sleep(0.05)
        in_flight -= 1
        return httpx.Response(200, json={"id": 1})

    respx.get(f"{BASE}/userProfile").mock(side_effect=counting_handler)
    cfg = _cfg(tmp_path, max_concurrent=4)
    c = YozhkaClient(cfg)
    await asyncio.gather(*(c.get_my_profile() for _ in range(8)))
    assert max_seen <= 4
    await c.aclose()
