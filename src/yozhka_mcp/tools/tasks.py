"""Тулы: задачи — CRUD, перемещение, приоритет, дедлайн, исполнители, метки, история."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..api import endpoints as ep
from ..api.client import YozhkaClient
from ._shared import (compact, render_html, page_info, run, strip_html,
                      write_guard)


def _deadline_to_ts(deadline: str) -> str:
    """'YYYY-MM-DD' -> ISO с 23:59:59 по Москве (MSK, +03:00) — таймзона hardcoded в API Ёжки."""
    return f"{deadline}T23:59:59+03:00"


async def _priority_id(client: YozhkaClient, priority: str | None) -> int:
    """Резолв названия приоритета в id; неизвестное — ошибка со списком (без молчаливых подмен)."""
    if priority is None:
        return 2
    priorities = await client.list_priorities()
    for p in priorities:
        if p["priorityName"].lower() == priority.lower():
            return p["id"]
    names = ", ".join(p["priorityName"] for p in priorities)
    raise ToolError(f"Неизвестный приоритет: {priority}. Доступны: {names}")


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_tasks(project_id: int, search_text: str = "", page: int = 0,
                         size: int = 100) -> dict:
        """[read-only] Задачи проекта ({content: [Task]} + пагинация). Компактные поля: id, code, title, statusId…"""
        result = await client.list_tasks(project_id, search_text=search_text,
                                         page=page, size=size)
        result["content"] = [compact(t) for t in result.get("content", [])]
        result["page"] = page_info(result)
        return result

    @mcp.tool
    async def search_tasks(project_id: int, search_text: str, page: int = 0,
                           size: int = 50) -> dict:
        """[read-only] Поиск задач проекта по тексту (+ пагинация)."""
        result = await client.search_tasks(project_id, search_text, page=page, size=size)
        result["content"] = [compact(t) for t in result.get("content", [])]
        result["page"] = page_info(result)
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
        status_id: int | None = None,
        deadline: str | None = None,
    ) -> dict:
        """[write] Создать задачу. priority: 'Низкий'|'Средний'|'Высокий'|'Критичный'.
        status_id — из list_board_columns ЭТОГО проекта (id колонок уникальны per-project);
        по умолчанию первая колонка. deadline: 'YYYY-MM-DD' (23:59:59 по Москве).
        В description: @[email] → живой тег, [текст](https://…) → живая ссылка."""
        async def _fn():
            priority_id = await _priority_id(client, priority)
            deadline_ts = _deadline_to_ts(deadline) if deadline else None
            body = await render_html(description, client.find_user_by_email) if description else ""
            task = await client.create_task(
                project_id, title, description=body, priority_id=priority_id,
                status_id=status_id, deadline_ts=deadline_ts,
            )
            return compact(task)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def update_task(task_code: str, title: str | None = None, description: str | None = None) -> dict:
        """[write] Изменить название и/или описание задачи. В description: @[email] → живой тег, [текст](https://…) → живая ссылка."""
        async def _fn():
            task = await client.get_task(task_code)
            if title is not None:
                task["title"] = title
            if description is not None:
                task["contentData"] = await render_html(description, client.find_user_by_email)
            updated = await client.update_task(task)
            result = compact(updated)
            result["description"] = strip_html(updated.get("contentData"))
            return result
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def move_task(task_code: str, status_id: int) -> dict:
        """[write] Переместить задачу в колонку (status_id из list_board_columns: дефолт 1..4 или кастомный)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["statusId"] = status_id
            updated = await client.update_task(task)
            return compact(updated)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def set_task_priority(task_code: str, priority: str) -> dict:
        """[write] Приоритет задачи: 'Низкий' | 'Средний' | 'Высокий' | 'Критичный' | 'Не задан'."""
        async def _fn():
            priority_id = await _priority_id(client, priority)
            task = await client.get_task(task_code)
            task["priorityId"] = priority_id
            updated = await client.update_task(task)
            return compact(updated)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def set_task_deadline(task_code: str, deadline: str | None = None) -> dict:
        """[write] Дедлайн задачи: 'YYYY-MM-DD' (23:59:59 по Москве) или null (снять = бессрочно)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["deadlineTs"] = _deadline_to_ts(deadline) if deadline else ep.FOREVER
            updated = await client.update_task(task)
            return compact(updated)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def set_task_executors(task_code: str, executor_ids: list[int]) -> dict:
        """[write] Назначить исполнителей задачи (id из list_project_users)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["executorsIds"] = executor_ids
            updated = await client.update_task(task)
            return compact(updated)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def set_task_tags(task_code: str, tag_ids: list[int], workspace_id: int) -> dict:
        """[write] Заменить метки задачи (id из list_tags). Неизвестный id — ошибка, без тихой фильтрации."""
        async def _fn():
            task = await client.get_task(task_code)
            tags_response = await client.list_tags(workspace_id)
            known = {t.get("id"): t for t in tags_response.get("content", [])}
            unknown = [i for i in tag_ids if i not in known]
            if unknown:
                raise ToolError(
                    f"Неизвестные tag_id: {unknown}. Доступны: {sorted(known)} (list_tags)"
                )
            task["tags"] = [known[i] for i in tag_ids]
            updated = await client.update_task(task)
            result = compact(updated)
            result["tags"] = updated.get("tags", [])
            return result
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def complete_task(task_code: str, completed: bool = True) -> dict:
        """[write] Отметить задачу выполненной/вернуть в работу (isCompleted)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["isCompleted"] = completed
            updated = await client.update_task(task)
            return compact(updated)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def delete_task(task_code: str) -> dict:
        """[write] Удалить задачу (необратимо!)."""
        async def _fn():
            task = await client.get_task(task_code)
            await client.delete_task(task["id"])
            return {"deleted": task_code, "id": task["id"]}
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def get_task_history(task_code: str, page: int = 0, size: int = 20) -> dict:
        """[read-only] История изменений задачи: кто/что/когда/старое→новое значение (+ пагинация)."""
        task = await client.get_task(task_code)
        result = await client.get_task_history(task["id"], page=page, size=size)
        result["page"] = page_info(result)
        return result

    @mcp.tool
    async def list_priorities() -> list:
        """[read-only] Справочник приоритетов (id ↔ название)."""
        return await client.list_priorities()

    # ---------- Глобальные списки ----------

    @mcp.tool
    async def list_my_tasks() -> list:
        """[read-only] Все мои задачи во всех пространствах (с дедлайнами и без, агрегация «ежедневника»)."""
        me = await client.get_my_profile()
        result: list = []
        workspaces = await client.list_workspaces(size=50)
        for ws in workspaces.get("content", []):
            for with_deadline in (True, False):
                tasks = await client.list_deadline_tasks(ws["id"], me["id"], with_deadline)
                items = tasks.get("content", []) if isinstance(tasks, dict) else (tasks or [])
                for t in items:
                    row = compact(dict(t))
                    row["workspaceCode"] = ws.get("code")
                    row["workspaceTitle"] = ws.get("title")
                    result.append(row)
        return result

    @mcp.tool
    async def list_deadline_tasks(workspace_id: int, with_deadline: bool = True,
                                  search: str = "") -> list:
        """[read-only] Мои задачи пространства: с дедлайнами (with_deadline=true, «ежедневник»)
        или без дедлайнов. search — фильтр по тексту."""
        me = await client.get_my_profile()
        tasks = await client.list_deadline_tasks(workspace_id, me["id"], with_deadline, search)
        items = tasks.get("content", []) if isinstance(tasks, dict) else (tasks or [])
        return [compact(t) for t in items]

    # ---------- Наблюдатели / копирование / перенос / повтор ----------

    @mcp.tool
    async def set_task_observers(task_code: str, user_ids: list[int]) -> dict:
        """[write] Назначить наблюдателей задачи (id из list_project_users)."""
        async def _fn():
            task = await client.get_task(task_code)
            task["observersIds"] = user_ids
            updated = await client.update_task(task)
            result = compact(updated)
            result["observersIds"] = updated.get("observersIds", [])
            return result
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def copy_task(task_code: str, target_project_id: int) -> dict:
        """[write] Копировать задачу в другой проект; возвращает новую задачу."""
        async def _fn():
            task = await client.get_task(task_code)
            new_task = await client.copy_task(task["id"], target_project_id)
            return compact(new_task)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def move_task_to_project(task_code: str, project_id: int) -> dict:
        """[write] Перенести задачу в другой проект (не путать с move_task — та меняет колонку)."""
        async def _fn():
            task = await client.get_task(task_code)
            updated = await client.move_task_to_project(task["id"], project_id)
            return compact(updated)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def set_task_repeat(
        task_code: str,
        enabled: bool,
        period: str = "WEEKLY",
        task_repeat_type: str = "COPY",
        days_of_week: list[str] | None = None,
        workdays_only: bool = False,
    ) -> dict:
        """[write] Повторяющаяся задача (PRO-тариф Ёжки). enabled=false — выключить.
        period: 'DAILY'|'WEEKLY'|'MONTHLY'|'ANNUALLY'; task_repeat_type: 'COPY' (новая копия)
        | 'MOVE' (при завершении пересоздаётся сама); days_of_week для WEEKLY:
        ['monday','tuesday',…]. Без PRO сервер вернёт ошибку — она придёт как есть."""
        async def _fn():
            period_u = period.upper()
            if period_u not in {"DAILY", "WEEKLY", "MONTHLY", "ANNUALLY"}:
                raise ToolError("period должен быть DAILY|WEEKLY|MONTHLY|ANNUALLY, получено: " + period)
            all_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            chosen = set(days_of_week or ["monday"])
            unknown_days = chosen - set(all_days)
            if unknown_days:
                raise ToolError(f"Неизвестные дни: {sorted(unknown_days)}. Доступны: {all_days}")
            task = await client.get_task(task_code)
            rs = task.get("repeatSetting") or {}
            rs.update({
                "enabled": enabled, "period": period_u,
                "type": task_repeat_type.upper(), "workdaysOnly": workdays_only,
                "daysOfWeek": {d: (d in chosen) for d in all_days},
            })
            task["repeatSetting"] = rs
            await client.update_task(task)
            # на бесплатном тарифе сервер может молча игнорировать поле —
            # возвращаем ФАКТИЧЕСКОЕ состояние после перечитки
            actual = await client.get_task(task_code)
            result = compact(actual)
            result["repeatSetting"] = actual.get("repeatSetting")
            return result
        return await run(write_guard(read_only, _fn))

    # ---------- Экспорт ----------

    @mcp.tool
    async def export_tasks(workspace_id: int, project_id: int, fmt: str = "xlsx",
                           save_dir: str | None = None) -> dict:
        """[read-only] Выгрузить задачи проекта в файл (fmt: 'xlsx'|'csv'); вернуть {path, size}."""
        if fmt not in ("xlsx", "csv"):
            raise ToolError("fmt должен быть xlsx или csv, получено: " + fmt)
        import tempfile
        from pathlib import Path
        data = await client.export_tasks(fmt, workspace_id, project_id, f"tasks-{project_id}.{fmt}")
        directory = Path(save_dir) if save_dir else Path(tempfile.gettempdir())
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"yozhka-tasks-{project_id}.{fmt}"
        path.write_bytes(data)
        return {"path": str(path), "size": len(data)}
