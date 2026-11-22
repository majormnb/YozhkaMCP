"""MCP-сервер Ёжки (FastMCP, stdio)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from .api.client import YozhkaClient
from .config import config

if config.debug:
    logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("yozhka_mcp")


@asynccontextmanager
async def lifespan(app: FastMCP):
    if not config.has_auth:
        logger.warning(
            "YOZHKA_REFRESH_TOKEN / YOZHKA_ACCESS_TOKEN не заданы — "
            "тулы будут возвращать ошибку аутентификации (см. README)"
        )
    yield
    await client.aclose()


client = YozhkaClient(config)
mcp = FastMCP(
    "Yozhka",
    instructions=(
        "Работа с канбан-планировщиком Ёжка (yozhka.lukit.ru): пространства, проекты, "
        "задачи, колонки, чек-листы, комментарии, участники. "
        "Идентификаторы: workspace/project — код (BMCPTESTX) или id; задача — код вида BMCPTESTX-1."
    ),
    lifespan=lifespan,
)

# Регистрация тулов по доменам (при READ_ONLY write-тулы не регистрируются)
from .tools import auth, checklists, columns, comments, misc, projects, tasks, workspaces  # noqa: E402

for module in (auth, workspaces, projects, columns, tasks, checklists, comments, misc):
    module.register(mcp, client, read_only=config.read_only)

# READ_ONLY: write-тулы не видны клиенту (плюс write_guard внутри каждого вызова — defense-in-depth)
_WRITE_TOOL_PREFIXES = (
    "create_", "update_", "delete_", "move_", "set_", "invite_",
    "archive_", "restore_", "toggle_", "complete_", "add_", "mark_",
)
if config.read_only:
    async def _hide_write_tools() -> set[str]:
        return {t.name for t in await mcp.list_tools()
                if t.name.startswith(_WRITE_TOOL_PREFIXES)}
    import asyncio as _aio
    _write_tools = _aio.run(_hide_write_tools())
    mcp.disable(names=_write_tools)
    logger.info("READ_ONLY: скрыто write-тулов: %d", len(_write_tools))

logger.info("Yozhka MCP: %s mode", "read-only" if config.read_only else "read-write")


def main() -> None:
    mcp.run()  # stdio по умолчанию


if __name__ == "__main__":
    main()
