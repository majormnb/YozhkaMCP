"""Общие хелперы для тулов."""

from __future__ import annotations

import re
from typing import Any, Callable

from fastmcp.exceptions import ToolError

from ..api import text as _text
from ..api.exceptions import YozhkaError

_TASK_FIELDS_SHORT = ("id", "code", "title", "projectId", "statusId", "statusName",
                      "priorityId", "deadlineTs", "executorsIds", "isCompleted")


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


async def run(fn: Callable) -> Any:
    """Выполнить работу тула, превратив ошибки API в понятный ToolError.

    Без этого читаемость сообщений зависит от настроек маскировки ошибок
    конкретного клиента/хостинга FastMCP.
    """
    try:
        return await fn()
    except YozhkaError as exc:
        raise ToolError(str(exc)) from exc


def compact(task: dict) -> dict:
    """Краткое представление задачи для списков (экономия токенов)."""
    return {k: task.get(k) for k in _TASK_FIELDS_SHORT}


def strip_html(value: Any) -> Any:
    """Убрать <p>…</p> обёртку из текстовых полей (пустая строка -> None)."""
    if not isinstance(value, str):
        return value
    text = re.sub(r"</?p[^>]*>", "", value).strip()
    return text or None


def wrap_html(value: str) -> str:
    """Безопасный HTML из текста: экранировать и обернуть в <p>…</p>.

    Сырой HTML больше не пропускается (stored-XSS): маркеры упоминаний @[email]
    экранирование переживают и подставляются после — через html_with_mentions.
    """
    return _text.wrap(_text.escape(value.strip()))


async def html_with_mentions(text: str, lookup: Callable) -> str:
    """Пайплайн безопасного HTML: escape → подстановка @[email]-упоминаний → <p>-обёртка.

    lookup — async функция email → список пользователей (client.find_user_by_email).
    Плейн-текст «@имя» остаётся текстом: Ёжка делает упоминание живым только span-тегом.
    """
    escaped = _text.escape(text)
    matches = {m.group(0): m.group(1).strip() for m in MENTION_RE.finditer(escaped)}
    for raw, email in matches.items():
        users = await lookup(email)
        if not users:
            raise ToolError(f"@[{email}]: пользователь не найден")
        user = users[0]
        mail = user.get("mail") or user.get("email") or ""
        span = _text.mention_span(user["id"], mail, user.get("displayName") or mail)
        escaped = escaped.replace(raw, span)
    return _text.wrap(escaped)


MENTION_RE = re.compile(r"@\[([^\]]+)\]")


def page_info(response: dict) -> dict:
    return {
        "totalElements": response.get("totalElements"),
        "totalPages": response.get("totalPages"),
        "pageNumber": response.get("pageNumber"),
    }
