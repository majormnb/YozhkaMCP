"""Фабрики полных тел запросов — API Ёжки требует ПОЛНЫЕ объекты на POST/PUT.

Держим в одном месте: при drift API правится здесь, а не в трёх методах клиента.
Текстовые поля принимают ГОТОВЫЙ HTML (экранирование/упоминания — tools/_shared).
"""

from __future__ import annotations

from typing import Any

from . import endpoints as ep


def task_body(
    project_id: int,
    title: str,
    *,
    status_id: int,
    description_html: str = "",
    priority_id: int = 2,
    executors_ids: list[int] | None = None,
    deadline_ts: str | None = None,
    tags: list[dict] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "projectId": project_id,
        "projectCode": "", "projectTitle": "", "projectIconColor": "", "projectIconUrl": "",
        "code": "",
        "hierarchyLevelId": ep.HIERARCHY_LEVEL_DEFAULT,
        "priorityId": priority_id,
        "statusId": status_id,
        "statusColor": "", "statusName": "",
        "typeId": ep.TASK_TYPE_DEFAULT,
        "contentData": description_html,
        "attachments": [],
        "orderNum": 0,
        "executorsIds": executors_ids or [],
        "observersIds": [],
        "notifications": [],
        "tags": tags or [],
        "entityType": "task",
        "isNew": False,
        "calendarId": None,
        "contentDataWithTags": "",
        "orderNumProjects": 0,
        "isCompleted": False,
        "workspaceCode": "",
        "repeatSetting": {
            "id": -1, "taskId": -1, "enabled": False, "type": "COPY",
            "targetStatusId": -1, "period": "DAILY", "workdaysOnly": True,
            "daysOfWeek": {"monday": True, "tuesday": False, "wednesday": False,
                           "thursday": False, "friday": False, "saturday": False, "sunday": False},
            "customValue": 1, "customPeriod": "DAY", "anchorDay": 1,
        },
    }
    if deadline_ts:
        body["deadlineTs"] = deadline_ts
    return body


def checklist_body(task_id: int, title_html: str, order_num: int = 1) -> dict[str, Any]:
    return {
        "taskId": task_id,
        "taskTitle": "", "taskCode": "", "taskStatusColor": "", "taskStatusName": "",
        "orderNum": order_num,
        "itemTitle": title_html,
        "itemAuthor": -1,
        "createTs": None, "updateTs": None,
        "markBy": None, "markTs": None, "markComment": None,
        "deadlineClTs": None, "itemChecked": False,
        "totalItemsCheckLists": 0,
        "entityType": "checklist",
        "itemTitleWithTags": "",
        "calendarId": None,
        "executorsIds": [],
    }


def comment_body(task_id: int, creator_id: int, text_html: str,
                 reply_to: int | None = None) -> dict[str, Any]:
    return {
        "contentComment": text_html,
        "creatorId": creator_id,
        "replyTo": reply_to,
        "taskId": task_id,
        "attachments": [],
        "attachIsPending": False,
        "replyToComment": {"replyText": ""},
        "contentCommentWithTags": "",
    }
