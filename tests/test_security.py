"""Тесты безопасности: экранирование HTML, упоминания, READ_ONLY, http-гвард."""

from __future__ import annotations

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from yozhka_mcp.api.text import mention_span
from yozhka_mcp.tools._shared import html_with_mentions, wrap_html

XSS = '<img src=x onerror="alert(1)">'
XSS_SCRIPT = "<script>alert(1)</script>"


# ---------- экранирование HTML ----------

async def test_html_with_mentions_escapes_xss():
    async def lookup(email):
        return []

    html = await html_with_mentions(f"привет {XSS}", lookup)
    assert "<img" not in html
    assert "&lt;img" in html
    assert "<p>" in html and "</p>" in html


def test_wrap_html_no_raw_passthrough():
    # раньше текст, начинающийся с "<", уходил в API как есть — stored-XSS
    html = wrap_html(XSS_SCRIPT)
    assert html == "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"


def test_wrap_html_escapes_quotes():
    assert "&quot;" in wrap_html('текст "с кавычками" и <b>жирным</b>')


# ---------- упоминания ----------

async def test_mention_span_escapes_hostile_display_name():
    # displayName контролируется ДРУГИМ пользователем Ёжки
    span = mention_span(17160, 'a@b.c', 'x" onmouseover="alert(1)')
    assert 'data-label="x&quot; onmouseover=&quot;alert(1)' in span
    assert 'onmouseover="alert' not in span  # атрибут не сломан


async def test_mention_span_id_must_be_numeric():
    with pytest.raises(ValueError):
        mention_span("17160,junk@x", "a@b.c", "Имя")  # id с мусором не проходит


async def test_html_with_mentions_builds_live_span():
    async def lookup(email):
        return [{"id": 5, "mail": "user@yandex.ru", "displayName": "Егор"}]

    html = await html_with_mentions("пинг @[user@yandex.ru] глянь", lookup)
    assert 'data-type="mention" data-id="5,user@yandex.ru" data-label="Егор"' in html
    assert "@[user@yandex.ru]" not in html


async def test_html_with_mentions_unknown_email_raises():
    async def lookup(email):
        return []

    with pytest.raises(ToolError):
        await html_with_mentions("пинг @[nope@nope.nope]", lookup)


async def test_html_with_mentions_escapes_rest_of_text():
    async def lookup(email):
        return [{"id": 5, "mail": "user@yandex.ru", "displayName": "Егор"}]

    html = await html_with_mentions(f"@[user@yandex.ru] {XSS}", lookup)
    assert "&lt;img" in html
    assert "<img" not in html


# ---------- READ_ONLY ----------

async def test_read_only_hides_all_write_tools():
    """Скрытие по docstring-тегу [write]: ни один write-тул не виден, включая convert_*."""
    from contextlib import asynccontextmanager

    from fastmcp import FastMCP

    from yozhka_mcp import server as srv
    from yozhka_mcp.tools import (auth, checklists, columns, comments,  # noqa: F401
                                  misc, projects, tasks, workspaces)

    @asynccontextmanager
    async def hide_write_tools(app):
        tools = await app.list_tools()
        write_tools = {t.name for t in tools if (t.description or "").startswith("[write]")}
        app.disable(names=write_tools)
        yield

    mcp = FastMCP("readonly-test", lifespan=hide_write_tools)
    for module in (srv.auth, srv.workspaces, srv.projects, srv.columns, srv.tasks,
                   srv.checklists, srv.comments, srv.misc):
        module.register(mcp, srv.client, read_only=True)

    async with Client(mcp) as c:
        tools = await c.list_tools()
        visible = {t.name for t in tools}
        assert "convert_checklist_item_to_task" not in visible  # регресс: префиксы его пропускали
        assert "create_task" not in visible
        assert "add_comment" not in visible
        assert "list_tasks" in visible


async def test_write_guard_blocks_even_if_registered():
    from fastmcp import FastMCP

    from yozhka_mcp import server as srv
    from yozhka_mcp.tools import checklists as module

    mcp = FastMCP("guard-test")
    module.register(mcp, srv.client, read_only=True)
    async with Client(mcp) as c:
        # тул зарегистрирован, но guard отклоняет вызов
        with pytest.raises(ToolError):
            await c.call_tool("add_checklist_item", {"task_code": "X-1", "title": "нет"})


# ---------- http-гвард ----------

async def test_http_guard_token():
    import httpx

    from yozhka_mcp import server as srv
    from yozhka_mcp.config import config

    async def dummy_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    config.http_token = "s3cret"
    try:
        app = srv._http_guard(dummy_app)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as hc:
            r = await hc.get("/mcp")
            assert r.status_code == 401
            r = await hc.get("/mcp", headers={"X-MCP-Token": "wrong"})
            assert r.status_code == 401
            r = await hc.get("/mcp", headers={"Authorization": "Bearer s3cret"})
            assert r.status_code == 200
    finally:
        config.http_token = None


async def test_http_guard_localhost_without_token():
    import httpx

    from yozhka_mcp import server as srv
    from yozhka_mcp.config import config

    async def dummy_app(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    assert config.http_token is None
    app = srv._http_guard(dummy_app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as hc:
        r = await hc.get("/mcp", headers={"host": "localhost:8000"})
        assert r.status_code == 200
        r = await hc.get("/mcp", headers={"host": "evil.example.com"})  # DNS-rebinding
        assert r.status_code == 403


# ---------- конфиг ----------

def test_base_url_rejects_plain_http_remote():
    from yozhka_mcp.config import Config

    os_env = {"YOZHKA_BASE_URL": "http://attacker.example"}
    monkey = pytest.MonkeyPatch()
    for k, v in os_env.items():
        monkey.setenv(k, v)
    try:
        with pytest.raises(ValueError):
            Config()
    finally:
        monkey.undo()
