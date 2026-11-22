"""Общие хелперы для тулов."""

from __future__ import annotations

import re
from typing import Any, Callable

from fastmcp.exceptions import ToolError

_TASK_FIELDS_SHORT = ("id", "code", "title", "statusId", "statusName", "priorityId",
                      "deadlineTs", "executorsIds", "isCompleted")


def write_guard(read_only: bool, fn: Callable) -> Callable:
    """Defense-in-depth: даже если write-тул зарегистрирован, в READ_ONLY — отказ."""
    if not read_only:
        return fn

    def guarded(*args, **kwargs):
        raise ToolError("YOZHKA_READ_ONLY=true: write-операции запрещены")

    guarded.__name__ = fn.__name__
    guarded.__doc__ = fn.__doc__
    guarded.__annotations__ = getattr(fn, "__annotations__", {})
    return guarded


def compact(task: dict) -> dict:
    """Краткое представление задачи для списков (экономия токенов)."""
    return {k: task.get(k) for k in _TASK_FIELDS_SHORT}


def strip_html(value: Any) -> Any:
    """Убрать <p>…</p> обёртку из текстовых полей."""
    if not isinstance(value, str):
        return value
    text = re.sub(r"</?p[^>]*>", "", value).strip()
    return text or None


def wrap_html(value: str) -> str:
    """Обернуть текст в <p>…</p> (API ждёт HTML для contentData/itemTitle/contentComment)."""
    value = value.strip()
    if value.startswith("<"):
        return value
    return f"<p>{value}</p>"


MENTION_RE = re.compile(r"@\[([^\]]+)\]")


def mention_html(user: dict) -> str:
    """Живой тег упоминания Ёжки (TipTap mention: span data-type="mention")."""
    mail = user.get("mail") or user.get("email") or ""
    name = user.get("displayName") or mail
    return f'<span data-type="mention" data-id="{user.get("id")},{mail}" data-label="{name}">@{name}</span>'


async def resolve_mentions(text: str, lookup) -> str:
    """Заменить @[email] в тексте на живые теги упоминания.

    lookup — async функция email → список пользователей (client.find_user_by_email).
    Плейн-текст «@имя» остаётся текстом: Ёжка делает упоминание живым только span-тегом.
    """
    matches = {m.group(0): m.group(1).strip() for m in MENTION_RE.finditer(text)}
    for raw, email in matches.items():
        users = await lookup(email)
        if not users:
            raise ToolError(f"@[{email}]: пользователь не найден")
        text = text.replace(raw, mention_html(users[0]))
    return text


def page_info(response: dict) -> dict:
    return {
        "totalElements": response.get("totalElements"),
        "totalPages": response.get("totalPages"),
        "pageNumber": response.get("pageNumber"),
    }
