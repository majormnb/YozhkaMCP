"""Тулы: аутентификация и профиль."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:
    @mcp.tool
    async def get_current_user() -> dict:
        """[read-only] Мой профиль в Ёжке: id, mail, displayName и роли."""
        return await client.get_my_profile()
