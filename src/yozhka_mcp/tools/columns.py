"""Тулы: колонки канбан-доски (статусы задач)."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient
from ._shared import write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_board_columns(project_id: int) -> list:
        """[read-only] Колонки доски: [{id, name, orderNum, statusColor}]. Дефолт: Новая, В работе, Закрыта, В ожидании."""
        return await client.list_columns(project_id)

    @mcp.tool
    async def create_column(project_id: int, name: str, color: str = "#5A688D") -> dict:
        """[write] Добавить колонку на доску (кастомный статус)."""
        async def _fn():
            return await client.create_column(project_id, name, color)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def update_column(project_id: int, task_status_id: int, name: str, color: str) -> dict:
        """[write] Переименовать колонку / сменить цвет (task_status_id из list_board_columns)."""
        async def _fn():
            return await client.update_column(project_id, task_status_id, name, color)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def delete_column(project_id: int, task_status_id: int) -> dict:
        """[write] Удалить колонку (в ней не должно быть задач)."""
        async def _fn():
            await client.delete_column(project_id, task_status_id)
            return {"deleted": task_status_id}
        return await write_guard(read_only, _fn)()
