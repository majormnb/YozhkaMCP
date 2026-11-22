"""Тулы: чек-листы задач."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient
from ._shared import strip_html, write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_checklist(task_code: str) -> dict:
        """[read-only] Чек-лист задачи: пункты, отметки, кто отметил."""
        task = await client.get_task(task_code)
        result = await client.list_checklist(task["id"])
        for item in result.get("content", []):
            item["title"] = strip_html(item.get("itemTitle"))
        return result

    @mcp.tool
    async def add_checklist_item(task_code: str, title: str) -> dict:
        """[write] Добавить пункт в чек-лист задачи."""
        async def _fn():
            task = await client.get_task(task_code)
            return await client.add_checklist_item(task["id"], title)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def mark_checklist_item(task_code: str, item_id: int, checked: bool = True) -> dict:
        """[write] Отметить/снять отметку пункта чек-листа (item_id из list_checklist)."""
        async def _fn():
            task = await client.get_task(task_code)
            return await client.mark_checklist_item(item_id, task["id"], checked)
        return await write_guard(read_only, _fn)()
