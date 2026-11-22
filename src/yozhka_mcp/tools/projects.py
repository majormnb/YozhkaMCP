"""Тулы: проекты — CRUD, архив, избранное, участники."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api import endpoints as ep
from ..api.client import YozhkaClient
from ._shared import write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_projects(workspace_id: int, state: str = "active", page: int = 1, size: int = 50) -> dict:
        """[read-only] Проекты пространства. state: active | favorite | archive."""
        return await client.list_projects(workspace_id, state_filter=state, page=page, size=size)

    @mcp.tool
    async def get_project(code: str, workspace_id: int) -> dict:
        """[read-only] Проект по коду (напр. REVENG) + id пространства."""
        return await client.get_project(code, workspace_id)

    @mcp.tool
    async def create_project(workspace_id: int, title: str, description: str | None = None) -> dict:
        """[write] Создать проект в пространстве (код сгенерируется по названию)."""
        async def _fn():
            return await client.create_project(workspace_id, title, description)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def update_project(code: str, workspace_id: int, title: str | None = None,
                             description: str | None = None) -> dict:
        """[write] Переименовать проект / изменить описание."""
        async def _fn():
            project = await client.get_project(code, workspace_id)
            if title is not None:
                project["title"] = title
            if description is not None:
                project["description"] = description
            return await client.update_project(project)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def archive_project(workspace_id: int, project_id: int) -> dict:
        """[write] Архивировать проект (перестаёт быть активным, восстановление возможно)."""
        async def _fn():
            await client.set_project_state(workspace_id, project_id, ep.PROJECT_STATE_ARCHIVE)
            return {"projectId": project_id, "state": "archived"}
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def restore_project(workspace_id: int, project_id: int) -> dict:
        """[write] Восстановить проект из архива."""
        async def _fn():
            await client.set_project_state(workspace_id, project_id, ep.PROJECT_STATE_ACTIVE)
            return {"projectId": project_id, "state": "active"}
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def toggle_project_favorite(project_id: int) -> dict:
        """[write] Переключить проект в/из избранного."""
        async def _fn():
            await client.toggle_project_favorite(project_id)
            return {"projectId": project_id, "favorite": "toggled"}
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def list_project_users(project_id: int) -> list:
        """[read-only] Участники проекта (users/activeUsers)."""
        return await client.list_project_users(project_id)
