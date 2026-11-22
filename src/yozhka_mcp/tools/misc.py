"""Тулы: пользователи и уведомления."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def find_user_by_email(email: str) -> list:
        """[read-only] Найти пользователя по email (id нужен для исполнителей)."""
        return await client.find_user_by_email(email)

    @mcp.tool
    async def list_notifications(size: int = 20) -> dict:
        """[read-only] Мои уведомления: {unreadCount, notifications[]}."""
        return await client.list_notifications(size=size)
