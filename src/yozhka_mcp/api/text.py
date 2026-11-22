"""Экранирование HTML для текстовых полей API Ёжки.

Ёжка рендерит contentData/contentComment/itemTitle как HTML в браузерах других
участников — неэкранированный текст превращается в stored-XSS. Правило: весь
пользовательский текст сначала экранируется, упоминания-спаны подставляются
ПОСЛЕ экранирования и собираются только из безопасных компонент.
"""

from __future__ import annotations

import html


def escape(text: str) -> str:
    """Экранировать пользовательский текст (в т.ч. кавычки — для атрибутов)."""
    return html.escape(text, quote=True)


def wrap(text_html: str) -> str:
    """Обернуть уже безопасный HTML в <p>…</p> (API ждёт параграф)."""
    return f"<p>{text_html}</p>"


def mention_span(user_id: int | str, mail: str, name: str) -> str:
    """Живой тег упоминания Ёжки (TipTap mention).

    id строго число, mail/name экранируются — displayName контролируется
    другим пользователем Ёжки и может содержать кавычки/угловые скобки.
    """
    uid = int(user_id)
    safe_mail = escape(str(mail or ""))
    safe_name = escape(str(name or ""))
    return f'<span data-type="mention" data-id="{uid},{safe_mail}" data-label="{safe_name}">@{safe_name}</span>'
