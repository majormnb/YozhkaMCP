"""Тулы: задачи — CRUD, перемещение, приоритет, дедлайн, исполнители, метки, история."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api import endpoints as ep
from ..api.client import YozhkaClient
from ._shared import compact, strip_html, wrap_html, write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_tasks(project_id: int, search_text: str = "", size: int = 100) -> dict:
        """[read-only] Задачи проекта ({content: [Task]}). Компактные поля: id, code, title, statusId…"""
        result = await client.list_tasks(project_id, search_text=search_text, size=size)
        result["content"] = [compact(t) for t in result.get("content", [])]
        return result

    @mcp.tool
    async def search_tasks(project_id: int, search_text: str, size: int = 50) -> dict:
        """[read-only] Поиск задач проекта по тексту."""
        result = await client.search_tasks(project_id, search_text, size=size)
        result["content"] = [compact(t) for t in result.get("content", [])]
        return result

    @mcp.tool
    async def get_task(task_code: str) -> dict:
        """[read-only] Задача по коду (напр. BMCPTESTX-1): все поля, включая описание и теги."""
        task = await client.get_task(task_code)
        task["description"] = strip_html(task.get("contentData"))
        return task

    @mcp.tool
    async def create_task(
        project_id: int,
        title: str,
        description: str = "",
        priority: str | None = None,
        status_id: int = 1,
        deadline: str | None = None,
    ) -> dict:
        """[write] Создать задачу. priority: 'Низкий'|'Средний'|'Высокий'|'Критичный'.
        deadline: 'YYYY-MM-DD' (23:59:59 местной таймзоны). status_id: 1 Новая, 2 В работе, 3 Закрыта, 4 В ожидании."""
        async def _fn():
            priority_id = 2
            if priority:
                priorities = await client.list_priorities()
                priority_id = next(
                    (p["id"] for p in priorities if p["priorityName"].lower() == priority.lower()), 2
                )
            deadline_ts = f"{deadline}T23:59:59+03:00" if deadline else None
            task = await client.create_task(
                project_id, title, description=description, priority_id=priority_id,
                status_id=status_id, deadline_ts=deadline_ts,
            )
            return compact(task)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def update_task(task_code: str, title: str | None = None, description: str | None = None) -> dict:
        """[write] Изменить название и/или описание задачи."""
        async def _fn():
            task = await client.get_task(task_code)
            if title is not None:
                task["title"] = title
            if description is not None:
                task["contentData"] = wrap_html(description)
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def move_task(task_code: str, status_id: int) -> dict:
        """[write] Переместить задачу в колонку (status_id из list_board_columns: 1..4 или кастомный)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["statusId"] = status_id
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def set_task_priority(task_code: str, priority: str) -> dict:
        """[write] Приоритет задачи: 'Низкий' | 'Средний' | 'Высокий' | 'Критичный' | 'Не задан'."""
        async def _fn():
            priorities = await client.list_priorities()
            priority_id = next(
                (p["id"] for p in priorities if p["priorityName"].lower() == priority.lower()), None
            )
            if priority_id is None:
                from fastmcp.exceptions import ToolError
                raise ToolError(f"Неизвестный приоритет: {priority}. Доступны: "
                                + ", ".join(p["priorityName"] for p in priorities))
            task = await client.get_task(task_code)
            task["priorityId"] = priority_id
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def set_task_deadline(task_code: str, deadline: str | None = None) -> dict:
        """[write] Дедлайн задачи: 'YYYY-MM-DD' или null (снять)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["deadlineTs"] = f"{deadline}T23:59:59+03:00" if deadline else ep.FOREVER
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def set_task_executors(task_code: str, executor_ids: list[int]) -> dict:
        """[write] Назначить исполнителей задачи (id из list_project_users)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["executorsIds"] = executor_ids
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def set_task_tags(task_code: str, tag_ids: list[int], workspace_id: int) -> dict:
        """[write] Заменить метки задачи (id из list_tags)."""
        async def _fn():
            task = await client.get_task(task_code)
            tags_response = await client.list_tags(workspace_id)
            task["tags"] = [t for t in tags_response.get("content", []) if t["id"] in tag_ids]
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def complete_task(task_code: str, completed: bool = True) -> dict:
        """[write] Отметить задачу выполненной/вернуть в работу (isCompleted)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["isCompleted"] = completed
            updated = await client.update_task(task)
            return compact(updated)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def delete_task(task_code: str) -> dict:
        """[write] Удалить задачу (необратимо!)."""
        async def _fn():
            task = await client.get_task(task_code)
            await client.delete_task(task["id"])
            return {"deleted": task_code, "id": task["id"]}
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def get_task_history(task_code: str, size: int = 20) -> dict:
        """[read-only] История изменений задачи: кто/что/когда/старое→новое значение."""
        task = await client.get_task(task_code)
        return await client.get_task_history(task["id"], size=size)

    @mcp.tool
    async def list_priorities() -> list:
        """[read-only] Справочник приоритетов (id ↔ название)."""
        return await client.list_priorities()
