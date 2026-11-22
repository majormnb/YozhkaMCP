"""Юнит-тесты API-клиента (respx-моки httpx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from yozhka_mcp.api.client import YozhkaClient
from yozhka_mcp.api.exceptions import AuthError
from yozhka_mcp.config import Config

BASE = "https://yozhka.lukit.ru/backend"


def _client(**kwargs) -> YozhkaClient:
    cfg = Config.__new__(Config)
    cfg.base_url = BASE
    cfg.access_token = "test-access"
    cfg.refresh_token = "test-refresh"
    cfg.read_only = False
    cfg.request_timeout = 5.0
    cfg.max_retries = 3
    cfg.debug = False
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return YozhkaClient(cfg)


@respx.mock
async def test_bearer_header_sent():
    respx.get(f"{BASE}/userProfile").respond(json={"id": 1, "mail": "a@b.c"})
    c = _client()
    data = await c.get_my_profile()
    assert data["id"] == 1
    request = respx.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-access"
    await c.aclose()


@respx.mock
async def test_list_projects_state_filter():
    route = respx.get(f"{BASE}/project/tiles/my").respond(json={"content": [{"id": 5, "title": "P"}], "totalElements": 1})
    c = _client()
    result = await c.list_projects(workspace_id=18122, state_filter="archive")
    assert result["totalElements"] == 1
    assert "archive" in str(route.calls.last.request.url)
    await c.aclose()


@respx.mock
async def test_refresh_on_401():
    respx.get(f"{BASE}/userProfile").mock(
        side_effect=[
            httpx.Response(401, json={"error": "expired"}),
            httpx.Response(200, json={"id": 7}),
        ]
    )
    refresh = respx.post(f"{BASE}/auth/refresh").respond(json={"accessToken": "new-access", "refreshToken": "new-refresh"})
    c = _client()
    data = await c.get_my_profile()
    assert data["id"] == 7
    assert c._access_token == "new-access"
    assert refresh.called
    await c.aclose()


@respx.mock
async def test_401_loop_is_bounded():
    """Регресс: невалидный access + живой refresh не должны давать бесконечный цикл."""
    respx.get(f"{BASE}/userProfile").respond(401, json={"error": "expired"})
    respx.post(f"{BASE}/auth/refresh").respond(json={"accessToken": "still-bad", "refreshToken": "r"})
    c = _client()
    with pytest.raises(AuthError):
        await c.get_my_profile()
    # один исходный запрос + ровно один повтор после refresh
    assert respx.calls.call_count >= 2
    gets = [r for r in respx.calls if r.request.url.path.endswith("/userProfile")]
    assert len(gets) == 2
    await c.aclose()


@respx.mock
async def test_refresh_empty_access_token_raises():
    respx.post(f"{BASE}/auth/refresh").respond(json={"accessToken": None, "refreshToken": "r"})
    c = _client(access_token=None)
    with pytest.raises(AuthError):
        await c.get_my_profile()
    await c.aclose()


@respx.mock
async def test_auth_error_without_tokens():
    respx.post(f"{BASE}/auth/refresh").respond(401, json={})
    c = _client(access_token=None, refresh_token=None)
    with pytest.raises(AuthError):
        await c.get_my_profile()
    await c.aclose()


@respx.mock
async def test_404_maps_to_not_found():
    respx.get(f"{BASE}/task/code/NOPE-1").respond(404, json={"message": "not found"})
    from yozhka_mcp.api.exceptions import NotFoundError
    c = _client()
    with pytest.raises(NotFoundError):
        await c.get_task("NOPE-1")
    await c.aclose()
