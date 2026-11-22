"""HTTP-клиент API Ёжки: Bearer-auth с авто-refresh, ретраи, маппинг ошибок."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..config import Config
from . import endpoints as ep
from .exceptions import (
    ApiError,
    AuthError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
    YozhkaError,
)

logger = logging.getLogger("yozhka_mcp")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, YozhkaError):
        return exc.status_code in _RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, asyncio.TimeoutError))


class YozhkaClient:
    """Асинхронный клиент поверх приватного REST API Ёжки.

    Access-токен короткоживущий (~1 ч): при 401 один раз делаем refresh
    (POST /auth/refresh с refreshToken, ~30 дней) и повторяем запрос.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._access_token: str | None = config.access_token
        self._refresh_token: str | None = config.refresh_token
        self._http = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.request_timeout,
            headers={"Accept": "application/json"},
        )

    # ---------- низкий уровень ----------

    async def aclose(self) -> None:
        await self._http.aclose()

    def _ensure_open(self) -> None:
        """httpx-клиент мог быть закрыт завершившимся lifespan'ом — пересоздаём."""
        if self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._config.base_url,
                timeout=self._config.request_timeout,
                headers={"Accept": "application/json"},
            )

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(multiplier=0.5, max=8),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        data: str | None = None,
        headers: dict[str, str] | None = None,
        _is_refresh: bool = False,
    ) -> Any:
        if not self._access_token and not _is_refresh:
            await self._refresh()

        req_headers: dict[str, str] = {}
        self._ensure_open()
        if self._access_token:
            req_headers["Authorization"] = f"Bearer {self._access_token}"
        if json_body is not None or data is not None:
            req_headers["Content-Type"] = "application/json"
        if headers:
            req_headers.update(headers)

        response = await self._http.request(
            method,
            path,
            params=params,
            content=data,
            json=json_body,
            headers=req_headers,
        )

        if response.status_code == 401 and not _is_refresh:
            refreshed = await self._refresh()
            if refreshed:
                return await self._request(
                    method, path, params=params, json_body=json_body, data=data,
                    headers=headers,
                )

        if response.status_code >= 400:
            self._raise_from_response(response)

        if response.status_code == 204 or not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            return response.json()
        return response.text

    def _raise_from_response(self, response: httpx.Response) -> None:
        status = response.status_code
        try:
            payload = response.json()
        except Exception:
            payload = response.text[:500]
        detail = payload if not isinstance(payload, str) else payload
        exc_type = {
            400: ValidationError,
            401: AuthError,
            403: PermissionDeniedError,
            404: NotFoundError,
            422: ValidationError,
            429: RateLimitError,
        }.get(status, ApiError)
        raise exc_type(f"HTTP {status}: {detail}", status_code=status, payload=payload)

    async def _refresh(self) -> bool:
        """POST /auth/refresh — обменять refreshToken на новый access (+refresh)."""
        if not self._refresh_token:
            raise AuthError(
                "Нет токена: задайте YOZHKA_REFRESH_TOKEN (см. README, как достать из браузера)"
            )
        response = await self._http.post(
            ep.AUTH_REFRESH,
            json={"refreshToken": self._refresh_token},
            headers={"Content-Type": "application/json"},
        )
        if response.status_code != 200:
            raise AuthError(
                f"Refresh failed ({response.status_code}): сессия истекла, "
                "получите новый refreshToken в браузере (README)",
                status_code=response.status_code,
            )
        data = response.json()
        self._access_token = data.get("accessToken")
        if data.get("refreshToken"):
            self._refresh_token = data["refreshToken"]
        logger.info("Access token refreshed")
        return True

    # ---------- Auth ----------

    async def get_me(self) -> dict:
        return await self._request("GET", ep.AUTH_ME)

    # ---------- Workspaces ----------

    async def list_workspaces(self, page: int = 1, size: int = 50) -> dict:
        return await self._request("GET", ep.WORKSPACE_MY, params={"page": page, "size": size})

    async def get_workspace(self, code: str) -> dict:
        return await self._request("GET", ep.WORKSPACE_BY_CODE.format(code=quote(code)))

    async def generate_workspace_code(self, title: str) -> str:
        return await self._request("POST", ep.WORKSPACE_GENERATE_MCODE, data=self._json_str(title))

    async def create_workspace(self, title: str, description: str = "", icon_color: str = "") -> dict:
        code = await self.generate_workspace_code(title)
        return await self._request("POST", ep.WORKSPACE, json_body={
            "title": title, "code": code, "description": description, "iconColor": icon_color,
        })

    async def update_workspace(self, workspace: dict) -> dict:
        return await self._request("PUT", ep.WORKSPACE, json_body=workspace)

    async def list_workspace_users(self, workspace_id: int) -> list:
        return await self._request("GET", ep.WORKSPACE_USERS.format(workspace_id=workspace_id))

    async def invite_workspace_users(self, workspace_id: int, mails: list[str], role_id: int = 16) -> Any:
        return await self._request("POST", ep.WORKSPACE_ADD_USERS.format(workspace_id=workspace_id),
                                   json_body={"mails": mails, "roleId": role_id})

    async def list_workspace_roles(self) -> list:
        return await self._request("GET", ep.WORKSPACE_ROLE_LIST)

    async def get_workspace_limits(self, workspace_id: int) -> dict:
        return await self._request("GET", ep.WORKSPACE_LIMITS.format(workspace_id=workspace_id))

    # ---------- Tags ----------

    async def list_tags(self, workspace_id: int, search: str | None = None, page: int = 0, size: int = 999) -> dict:
        params: dict[str, Any] = {"page": page, "size": size}
        if search:
            params["search"] = search
        return await self._request("GET", ep.WORKSPACE_TAG.format(workspace_id=workspace_id), params=params)

    async def create_tag(self, workspace_id: int, tag_name: str, background_color: str = "var(--color-result_10)") -> dict:
        return await self._request("POST", ep.WORKSPACE_TAG_CREATE, json_body={
            "tagName": tag_name, "workspaceId": workspace_id, "backgroundColor": background_color,
        })

    # ---------- Projects ----------

    async def list_projects(self, workspace_id: int, state_filter: str = "active", page: int = 1, size: int = 50) -> dict:
        import json as _json
        state_map = {
            "active": {"active": True, "favorite": False, "blocked": False},
            "favorite": {"favorite": True, "blocked": False},
            "archive": {"archive": True, "blocked": True},
        }
        sf = _json.dumps(state_map.get(state_filter, state_map["active"]))
        return await self._request("GET", ep.PROJECT_TILES_MY, params={
            "page": page, "size": size, "workspaceId": workspace_id, "stateFilter": sf,
        })

    async def get_project(self, code: str, workspace_id: int) -> dict:
        return await self._request("GET", ep.PROJECT_BY_CODE.format(code=quote(code), workspace_id=workspace_id))

    async def generate_project_code(self, project_name: str, workspace_id: int) -> str:
        return await self._request("POST", ep.PROJECT_GENERATE_MCODE,
                                   params={"projectName": project_name, "workspaceId": workspace_id})

    async def create_project(self, workspace_id: int, title: str, description: str | None = None) -> dict:
        code = await self.generate_project_code(title, workspace_id)
        body = {"workspaceId": workspace_id, "title": title, "code": code,
                "iconColor": "", "iconName": "", "iconUrl": ""}
        project = await self._request("POST", ep.PROJECT, json_body=body)
        if description:
            project["description"] = description
            project = await self.update_project(project)
        return project

    async def update_project(self, project: dict) -> dict:
        return await self._request("PUT", ep.PROJECT, json_body=project)

    async def set_project_state(self, workspace_id: int, project_id: int, target_state_id: int) -> Any:
        return await self._request("POST", ep.PROJECT_UPDATE_STATE, params={
            "workspaceId": workspace_id, "projectId": project_id,
            "targetProjectStateId": target_state_id,
        })

    async def toggle_project_favorite(self, project_id: int) -> Any:
        return await self._request("POST", ep.PROJECT_FAVORITES.format(project_id=project_id))

    async def list_project_users(self, project_id: int) -> list:
        return await self._request("GET", ep.PROJECT_USERS.format(project_id=project_id))

    # ---------- Колонки ----------

    async def list_columns(self, project_id: int) -> list:
        return await self._request("GET", ep.WORKFLOW_STATUSES, params={"projectId": project_id})

    async def create_column(self, project_id: int, status_name: str, status_color: str = "#5A688D") -> dict:
        return await self._request("POST", ep.WORKFLOW_STATUSES, json_body={
            "projectId": project_id, "statusName": status_name, "statusColor": status_color,
        })

    async def update_column(self, project_id: int, task_status_id: int, status_name: str, status_color: str) -> dict:
        return await self._request("PUT", ep.WORKFLOW_STATUSES, json_body={
            "projectId": project_id, "taskStatusId": task_status_id,
            "statusName": status_name, "statusColor": status_color,
        })

    async def delete_column(self, project_id: int, task_status_id: int) -> Any:
        return await self._request("DELETE", ep.WORKFLOW_STATUSES, json_body={
            "projectId": project_id, "taskStatusId": task_status_id,
        })

    # ---------- Tasks ----------

    async def list_tasks(self, project_id: int, search_text: str = "", page: int = 0, size: int = 200) -> dict:
        return await self._request("GET", ep.TASK_LIST.format(project_id=project_id),
                                   params={"page": page, "size": size, "searchText": search_text})

    async def search_tasks(self, project_id: int, search_text: str, page: int = 0, size: int = 50) -> dict:
        return await self._request("GET", ep.TASK_SEARCH.format(project_id=project_id),
                                   params={"page": page, "size": size, "searchText": search_text})

    async def get_task(self, task_code: str) -> dict:
        return await self._request("GET", ep.TASK_BY_CODE.format(task_code=quote(task_code)))

    async def create_task(
        self,
        project_id: int,
        title: str,
        *,
        description: str = "",
        priority_id: int = 2,
        status_id: int | None = None,
        executors_ids: list[int] | None = None,
        deadline_ts: str | None = None,
        tags: list[dict] | None = None,
    ) -> dict:
        # Статусы уникальны для проекта (кастомные колонки меняют id) — резолвим из живого воркфлоу
        columns = await self.list_columns(project_id)
        valid_ids = {c["id"] for c in columns}
        if status_id is None or status_id not in valid_ids:
            first = min(columns, key=lambda c: c.get("orderNum", 0))
            status_id = first["id"]
        body = {
            "title": title,
            "projectId": project_id,
            "projectCode": "", "projectTitle": "", "projectIconColor": "", "projectIconUrl": "",
            "code": "",
            "hierarchyLevelId": ep.HIERARCHY_LEVEL_DEFAULT,
            "priorityId": priority_id,
            "statusId": status_id,
            "statusColor": "", "statusName": "",
            "typeId": ep.TASK_TYPE_DEFAULT,
            "contentData": f"<p>{description}</p>" if description else "",
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
        return await self._request("POST", ep.TASK, params={"onTop": "true"}, json_body=body)

    async def update_task(self, task: dict) -> dict:
        """PUT /task требует ПОЛНЫЙ объект задачи (get_task → мутация → update_task)."""
        return await self._request("PUT", ep.TASK, json_body=task)

    async def delete_task(self, task_id: int) -> Any:
        return await self._request("DELETE", ep.TASK_BY_ID.format(task_id=task_id))

    async def list_priorities(self) -> list:
        return await self._request("GET", ep.TASK_PRIORITY)

    async def get_task_history(self, task_id: int, page: int = 0, size: int = 20) -> dict:
        return await self._request("GET", ep.TASK_HISTORY.format(task_id=task_id),
                                   params={"page": page, "size": size, "search": "", "filter": "{}"})

    # ---------- Чек-листы ----------

    async def list_checklist(self, task_id: int) -> dict:
        return await self._request("GET", ep.CHECKLIST_LIST.format(task_id=task_id),
                                   params={"page": 0, "size": 9999, "searchText": ""})

    async def add_checklist_item(self, task_id: int, title: str, order_num: int = 1) -> dict:
        return await self._request("POST", ep.CHECKLIST, json_body={
            "taskId": task_id,
            "taskTitle": "", "taskCode": "", "taskStatusColor": "", "taskStatusName": "",
            "orderNum": order_num,
            "itemTitle": f"<p>{title}</p>",
            "itemAuthor": -1,
            "createTs": None, "updateTs": None,
            "markBy": None, "markTs": None, "markComment": None,
            "deadlineClTs": None, "itemChecked": False,
            "totalItemsCheckLists": 0,
            "entityType": "checklist",
            "itemTitleWithTags": "",
            "calendarId": None,
            "executorsIds": [],
        })

    async def mark_checklist_item(self, item_id: int, task_id: int, checked: bool) -> dict:
        # Коварность API: returnValue = СТАРОЕ значение чекбокса, сервер инвертирует его
        return await self._request("POST", ep.CHECKLIST_MARK.format(item_id=item_id), json_body={
            "itemId": item_id, "taskId": task_id, "returnValue": not checked,
        })

    # ---------- Комментарии ----------

    async def list_comments(self, task_id: int, page: int = 0, size: int = 20) -> dict:
        return await self._request("GET", ep.COMMENT_LIST.format(task_id=task_id),
                                   params={"page": page, "size": size, "search": "", "filter": "{}"})

    async def add_comment(self, task_id: int, creator_id: int, text: str, reply_to: int | None = None) -> dict:
        return await self._request("POST", ep.COMMENT, json_body={
            "contentComment": f"<p>{text}</p>",
            "creatorId": creator_id,
            "replyTo": reply_to,
            "taskId": task_id,
            "attachments": [],
            "attachIsPending": False,
            "replyToComment": {"replyText": ""},
            "contentCommentWithTags": "",
        })

    # ---------- Пользователи ----------

    async def get_my_profile(self) -> dict:
        result = await self._request("GET", ep.USER_PROFILE)
        if isinstance(result, list):  # API возвращает массив с одним элементом
            return result[0] if result else {}
        return result

    async def find_user_by_email(self, email: str) -> list:
        return await self._request("GET", ep.USER_PROFILE_FIND.format(email=quote(email)))

    # ---------- Уведомления ----------

    async def list_notifications(self, page: int = 1, size: int = 20) -> dict:
        return await self._request("GET", ep.NOTIFICATIONS, params={"page": page, "size": size, "search": ""})

    # ---------- утилиты ----------

    @staticmethod
    def _json_str(value: str) -> str:
        import json as _json
        return _json.dumps(value)  # generateMCode ждёт JSON-строку "Название"
