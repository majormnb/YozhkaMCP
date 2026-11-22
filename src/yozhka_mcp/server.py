"""MCP-сервер Ёжки (FastMCP, stdio/http)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .api.client import YozhkaClient
from .config import config

if config.debug:
    logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yozhka_mcp")

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1", "0.0.0.0"}


def _http_guard(app):
    """ASGI-гвард для http-режима: YOZHKA_HTTP_TOKEN; без него — только localhost.

    Эндпоинт без авторизации = полный доступ к аккаунту Ёжки у любого процесса,
    дотянувшегося до порта (включая DNS-rebinding из браузера).
    """
    async def guarded(scope, receive, send):
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            if config.http_token:
                ok = (headers.get("authorization") == f"Bearer {config.http_token}"
                      or headers.get("x-mcp-token") == config.http_token)
                status, message = 401, b"Unauthorized: wrong or missing YOZHKA_HTTP_TOKEN"
            else:
                host = (headers.get("host") or "").split(":")[0].lower()
                ok = not host or host in _LOCAL_HOSTS
                status, message = 403, b"Forbidden: set YOZHKA_HTTP_TOKEN to serve beyond localhost"
            if not ok:
                await send({"type": "http.response.start", "status": status,
                            "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
                await send({"type": "http.response.body", "body": message})
                return
        await app(scope, receive, send)
    return guarded


@asynccontextmanager
async def lifespan(app: FastMCP):
    if not config.has_auth:
        logger.warning(
            "YOZHKA_REFRESH_TOKEN / YOZHKA_ACCESS_TOKEN не заданы — "
            "тулы будут возвращать ошибку аутентификации (см. README)"
        )
    if config.read_only:
        # Скрытие по docstring-тегу [write] — самосогласовано с разметкой тулов
        # (префиксы имён пропускали convert_checklist_item_to_task).
        tools = await app.list_tools()
        write_tools = {t.name for t in tools if (t.description or "").startswith("[write]")}
        app.disable(names=write_tools)
        logger.info("READ_ONLY: скрыто write-тулов: %d", len(write_tools))
    yield
    await client.aclose()


client = YozhkaClient(config)
mcp = FastMCP(
    "Yozhka",
    instructions=(
        "Работа с канбан-планировщиком Ёжка (yozhka.lukit.ru): пространства, проекты, "
        "задачи, колонки, чек-листы, комментарии, участники. "
        "Идентификаторы: workspace/project — код (BMCPTESTX) или id; задача — код вида BMCPTESTX-1. "
        "ПОЛИТИКА ПОДТВЕРЖДЕНИЙ: в задаче, созданной ДРУГИМ пользователем, изменение title и/или "
        "description, а также удаление ЛЮБОЙ задачи (включая свою) без параметра confirm=True "
        "возвращают confirmation_required и ничего не делают. В этом случае покажи пользователю "
        "вопрос из поля message и дождись явного согласия («да», «подтверждаю»). НИКОГДА не передавай "
        "confirm=True по собственной инициативе — только после прямого ответа пользователя. "
        "В СВОИХ задачах изменение title/description — без гейта; перемещение, комментарии — всегда без."
    ),
    lifespan=lifespan,
)

# Регистрация тулов по доменам (READ_ONLY скрывает [write]-тулы в lifespan)
from .tools import (auth, attachments, checklists, columns, comments,  # noqa: E402
                    misc, projects, tasks, workspaces)

for module in (auth, workspaces, projects, columns, tasks, checklists,
               comments, attachments, misc):
    module.register(mcp, client, read_only=config.read_only)

logger.info("Yozhka MCP: %s mode", "read-only" if config.read_only else "read-write")


def main() -> None:
    if config.transport in {"http", "streamable-http", "sse"}:
        # Сервис-режим: YOZHKA_TRANSPORT=http (+ YOZHKA_HOST/PORT и YOZHKA_HTTP_TOKEN)
        import uvicorn

        app = mcp.http_app(path="/mcp",
                           transport="sse" if config.transport == "sse" else "streamable-http")
        uvicorn.run(_http_guard(app), host=config.host, port=config.port)
    else:
        mcp.run()  # stdio по умолчанию


if __name__ == "__main__":
    main()
