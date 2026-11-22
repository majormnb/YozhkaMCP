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
    async def add_comment(task_code: str, text: str, reply_to: int | None = None) -> dict:
        """[write] Добавить комментарий к задаче. reply_to — id комментария (ответ)."""
        async def _fn():
            task = await client.get_task(task_code)
            me = await client.get_my_profile()
            return await client.add_comment(task["id"], me["id"], text, reply_to=reply_to)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def update_comment(task_code: str, comment_id: int, text: str) -> dict:
        """[write] Редактировать комментарий (comment_id из list_comments, обычно свой)."""
        async def _fn():
            task = await client.get_task(task_code)
            comment = await client.get_comment(task["id"], comment_id)
            comment["contentComment"] = f"<p>{text}</p>"
            updated = await client.update_comment(comment)
            updated["text"] = strip_html(updated.get("contentComment"))
            return updated
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def delete_comment(task_code: str, comment_id: int) -> dict:
        """[write] Удалить комментарий (comment_id из list_comments)."""
        async def _fn():
            await client.delete_comment(comment_id)
            return {"deleted": comment_id}
        return await write_guard(read_only, _fn)()
