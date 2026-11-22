"""Тулы: пространства (workspaces) — CRUD, участники, роли, лимиты, метки."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..api.client import YozhkaClient
from ._shared import page_info, run, write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_workspaces(page: int = 1, size: int = 50) -> dict:
        """[read-only] Мои пространства: {content: [{id, title, code, userWorkspaceAuthorities…}]}."""
        return await client.list_workspaces(page=page, size=size)

    @mcp.tool
    async def get_workspace(code: str) -> dict:
        """[read-only] Пространство по коду (напр. BMCPTESTX): детали, подписка, полномочия."""
        return await client.get_workspace(code)

    @mcp.tool
    async def create_workspace(title: str, description: str = "") -> dict:
        """[write] Создать пространство. Код сгенерируется автоматически по названию."""
        async def _fn():
            return await client.create_workspace(title=title, description=description)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def update_workspace(code: str, title: str | None = None, description: str | None = None) -> dict:
        """[write] Переименовать/изменить описание пространства (PUT полного объекта)."""
        async def _fn():
            ws = await client.get_workspace(code)
            if title is not None:
                ws["title"] = title
            if description is not None:
                ws["description"] = description
            return await client.update_workspace(ws)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def list_workspace_users(workspace_id: int) -> list:
        """[read-only] Участники пространства (приглашённые без подтверждения — id: null)."""
        return await client.list_workspace_users(workspace_id)

    @mcp.tool
    async def invite_workspace_users(workspace_id: int, mails: list[str], role: str = "Участник") -> dict:
        """[write] Пригласить участников по email. Роль: 'Участник' | 'Администратор' | 'Владелец' (list_workspace_roles)."""
        async def _fn():
            roles = await client.list_workspace_roles()
            role_map = {r["roleName"]: r["roleId"] for r in roles}
            if role not in role_map:
                raise ToolError(
                    f"Неизвестная роль: {role!r}. Доступны: {sorted(role_map)} (list_workspace_roles)"
                )
            await client.invite_workspace_users(workspace_id, mails, role_map[role])
            return {"invited": mails, "role": role}
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def list_workspace_roles() -> list:
        """[read-only] Роли пространства: Владелец/Администратор/Участник (roleId)."""
        return await client.list_workspace_roles()

    @mcp.tool
    async def get_workspace_limits(workspace_id: int) -> dict:
        """[read-only] Лимиты тарифа: участники, проекты, вложения."""
        return await client.get_workspace_limits(workspace_id)

    @mcp.tool
    async def list_tags(workspace_id: int, search: str | None = None, page: int = 0) -> dict:
        """[read-only] Метки пространства: {content: [{id, tagName, backgroundColor}]} + пагинация."""
        result = await client.list_tags(workspace_id, search=search, page=page)
        result["page"] = page_info(result)
        return result

    @mcp.tool
    async def create_tag(workspace_id: int, tag_name: str) -> dict:
        """[write] Создать метку в пространстве."""
        async def _fn():
            return await client.create_tag(workspace_id, tag_name)
        return await run(write_guard(read_only, _fn))
