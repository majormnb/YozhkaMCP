"""Тулы: пользователи и уведомления."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient
from ._shared import page_info, run, write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def find_user_by_email(email: str) -> list:
        """[read-only] Найти пользователя по email (id нужен для исполнителей)."""
        return await client.find_user_by_email(email)

    @mcp.tool
    async def list_notifications(page: int = 1, size: int = 20) -> dict:
        """[read-only] Мои уведомления: {unreadCount, notifications[]} (+ пагинация)."""
        result = await client.list_notifications(page=page, size=size)
        result["page"] = page_info(result)
        return result

    @mcp.tool
    async def ack_notifications() -> dict:
        """[write] Отметить все уведомления прочитанными."""
        async def _fn():
            await client.ack_notifications()
            return {"acked": True}
        return await run(write_guard(read_only, _fn))
