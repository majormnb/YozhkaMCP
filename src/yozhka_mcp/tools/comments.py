"""Тулы: комментарии задач."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient
from ._shared import strip_html, write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_comments(task_code: str, size: int = 20) -> dict:
        """[read-only] Комментарии задачи (новые сверху, пагинация)."""
        task = await client.get_task(task_code)
        result = await client.list_comments(task["id"], size=size)
        for c in result.get("content", []):
            c["text"] = strip_html(c.get("contentComment"))
        return result

    @mcp.tool
    async def add_comment(task_code: str, text: str) -> dict:
        """[write] Добавить комментарий к задаче."""
        async def _fn():
            task = await client.get_task(task_code)
            me = await client.get_my_profile()
            return await client.add_comment(task["id"], me["id"], text)
        return await write_guard(read_only, _fn)()
