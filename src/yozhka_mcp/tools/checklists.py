"""Тулы: чек-листы задач."""

from __future__ import annotations

from fastmcp import FastMCP

from ..api.client import YozhkaClient
from ._shared import compact, html_with_mentions, run, strip_html, write_guard


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
        """[write] Добавить пункт в чек-лист задачи. Упоминания: @[email] → живой тег."""
        async def _fn():
            task = await client.get_task(task_code)
            html = await html_with_mentions(title, client.find_user_by_email)
            existing = await client.list_checklist(task["id"])
            order = max((i.get("orderNum", 0) for i in existing.get("content", [])), default=0) + 1
            return await client.add_checklist_item(task["id"], html, order_num=order)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def mark_checklist_item(task_code: str, item_id: int, checked: bool = True) -> dict:
        """[write] Отметить/снять отметку пункта чек-листа (item_id из list_checklist)."""
        async def _fn():
            task = await client.get_task(task_code)
            return await client.mark_checklist_item(item_id, task["id"], checked)
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def update_checklist_item(
        task_code: str,
        item_id: int,
        title: str | None = None,
        deadline: str | None = None,
        executor_ids: list[int] | None = None,
    ) -> dict:
        """[write] Изменить пункт чек-листа: title — название; deadline — 'YYYY-MM-DD'
        ('' — снять дату); executor_ids — id исполнителей ([] — снять всех).
        Не указанные параметры не меняются. item_id из list_checklist."""
        async def _fn():
            task = await client.get_task(task_code)
            item = await client.get_checklist_item(task["id"], item_id)
            if title is not None:
                item["itemTitle"] = await html_with_mentions(title, client.find_user_by_email)
            if deadline is not None:
                item["deadlineClTs"] = f"{deadline}T23:59:59+03:00" if deadline else None
            if executor_ids is not None:
                item["executorsIds"] = executor_ids
            # PUT /checklist отвечает пустым телом — перечитываем пункт для подтверждения
            await client.update_checklist_item(item)
            updated = await client.get_checklist_item(task["id"], item_id)
            updated["title"] = strip_html(updated.get("itemTitle"))
            return updated
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def delete_checklist_item(task_code: str, item_id: int) -> dict:
        """[write] Удалить пункт чек-листа (item_id из list_checklist)."""
        async def _fn():
            await client.delete_checklist_item(item_id)
            return {"deleted": item_id}
        return await write_guard(read_only, _fn)()

    @mcp.tool
    async def convert_checklist_item_to_task(task_code: str, item_id: int) -> dict:
        """[write] Преобразовать пункт чек-листа в отдельную задачу (пункт удаляется).
        Переносит название, исполнителей и дату. Возвращает новую задачу."""
        async def _fn():
            task = await client.get_task(task_code)
            item = await client.get_checklist_item(task["id"], item_id)
            title = strip_html(item.get("itemTitle"))
            if not title:
                from fastmcp.exceptions import ToolError
                raise ToolError(f"Пункт {item_id} без названия — нечего переносить в задачу")
            new_task = await client.create_task(
                project_id=task["projectId"],
                title=title,
                executors_ids=item.get("executorsIds") or [],
                deadline_ts=item.get("deadlineClTs"),
            )
            await client.delete_checklist_item(item_id)
            return compact(new_task)
        return await run(write_guard(read_only, _fn))
