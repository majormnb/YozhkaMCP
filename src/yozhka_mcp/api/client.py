"""HTTP-клиент API Ёжки: Bearer-auth с авто-refresh, ретраи, маппинг ошибок."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ..config import Config, config as app_config
from . import bodies, endpoints as ep
from .exceptions import (
    ApiError,
    AuthError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
    YozhkaError,
)
from .token_store import TokenStore

logger = logging.getLogger("yozhka_mcp")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRY_AFTER_CAP = 30.0  # сек — даже если сервер попросил больше


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, YozhkaError):
        return exc.status_code in _RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, asyncio.TimeoutError))


def _wait(retry_state) -> float:
    """Уважаем Retry-After при 429, иначе экспоненциальный джиттер."""
    outcome = getattr(retry_state, "outcome", None)
    exc = outcome.exception() if outcome else None
    if isinstance(exc, RateLimitError) and exc.retry_after is not None:
        return min(float(exc.retry_after), _RETRY_AFTER_CAP)
    return wait_exponential_jitter(multiplier=0.5, max=8)(retry_state)


class YozhkaClient:
    """Асинхронный клиент поверх приватного REST API Ёжки.

    Access-токен короткоживущий (~1 ч): при 401 один раз делаем refresh
    (POST /auth/refresh с refreshToken, ~30 дней) и повторяем запрос.
    """

    def __init__(self, config: Config) -> None:
        self._config = config
        self._access_token: str | None = config.access_token
        self._refresh_token: str | None = config.refresh_token
        self._refresh_lock = asyncio.Lock()
        self._sem = asyncio.Semaphore(config.max_concurrent)
        # Вечный режим: берём новейшую пару токенов из кеша на диске; если в .env
        # положили более свежий токен (fingerprint не совпал) — он выигрывает.
        self._store = TokenStore(Path(config.token_cache_path)) if config.token_cache_path else None
        if self._store:
            self._refresh_token, self._access_token = self._store.load(
                config.refresh_token, config.access_token)
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
        stop=stop_after_attempt(app_config.max_retries),
        wait=_wait,
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
        files: dict[str, Any] | None = None,
        _is_refresh: bool = False,
        _auth_retried: bool = False,
        _raw: bool = False,
    ) -> Any:
        self._ensure_open()  # клиент мог закрыть завершившийся lifespan — до любых запросов
        if not self._access_token and not _is_refresh:
            await self._refresh()

        req_headers: dict[str, str] = {}
        if self._access_token:
            req_headers["Authorization"] = f"Bearer {self._access_token}"
        if (json_body is not None or data is not None) and not files:
            req_headers["Content-Type"] = "application/json"
        if headers:
            req_headers.update(headers)

        # лимит параллельности: лишние запросы ждут локально, не долбя API
        async with self._sem:
            response = await self._http.request(
                method,
                path,
                params=params,
                content=None if files else data,   # с files= поле data уходит как form-field
                data=data if files else None,
                json=json_body,
                headers=req_headers,
                files=files,
            )

        # одна повторная попытка после 401: без флага невалидный access + живой refresh = бесконечный цикл
        if response.status_code == 401 and not _is_refresh and not _auth_retried:
            await self._refresh()
            return await self._request(
                method, path, params=params, json_body=json_body, data=data,
                headers=headers, files=files,
                _auth_retried=True,
            )

        if response.status_code >= 400:
            self._raise_from_response(response)

        if _raw:  # blob (экспорт xlsx/csv, скачивание вложений)
            return response.content
        if response.status_code == 204 or not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "json" in content_type:
            try:
                return response.json()
            except ValueError:
                # коварность: generateMCode и др. шлют плоский текст с content-type: json
                return response.text
        return response.text

    def _raise_from_response(self, response: httpx.Response) -> None:
        status = response.status_code
        try:
            payload = response.json()
        except Exception:
            payload = response.text[:500]
        detail = payload.get("message") or payload.get("text") or payload \
            if isinstance(payload, dict) else payload
        exc_type = {
            400: ValidationError,
            401: AuthError,
            403: PermissionDeniedError,
            404: NotFoundError,
            422: ValidationError,
            429: RateLimitError,
        }.get(status, ApiError)
        kwargs: dict[str, Any] = {}
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                kwargs["retry_after"] = int(retry_after)
        raise exc_type(f"HTTP {status}: {detail}", status_code=status, payload=payload, **kwargs)

    async def _refresh(self) -> bool:
        """POST /auth/refresh — обменять refreshToken на новый access (+refresh)."""
        if not self._refresh_token:
            raise AuthError(
                "Нет токена: задайте YOZHKA_REFRESH_TOKEN (см. README, как достать из браузера)"
            )
        access_before = self._access_token
        async with self._refresh_lock:
            # пока ждали лок, параллельный запрос мог уже обновить токены
            if self._access_token and self._access_token != access_before:
                return True
            self._ensure_open()
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
            access = data.get("accessToken")
            if not access:
                raise AuthError(
                    "Refresh вернул пустой accessToken — сессия истекла, "
                    "получите новый refreshToken в браузере (README)"
                )
            self._access_token = access
            if data.get("refreshToken"):
                self._refresh_token = data["refreshToken"]
            if self._store:  # вечный режим: новейшая пара токенов — на диск (0600)
                self._store.save(self._refresh_token, self._access_token,
                                 self._config.refresh_token)
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
        if not columns:
            raise YozhkaError(f"У проекта {project_id} нет колонок (workflowStatusesAvail пуст)")
        if status_id is None:
            status_id = min(columns, key=lambda c: c.get("orderNum", 0))["id"]
        elif status_id not in {c["id"] for c in columns}:
            valid = sorted(c["id"] for c in columns)
            raise YozhkaError(
                f"status_id={status_id} не существует в проекте {project_id}; "
                f"доступны {valid} (list_board_columns)"
            )
        body = bodies.task_body(
            project_id, title, status_id=status_id, description_html=description,
            priority_id=priority_id, executors_ids=executors_ids,
            deadline_ts=deadline_ts, tags=tags,
        )
        return await self._request("POST", ep.TASK, params={"onTop": "true"}, json_body=body)

    async def update_task(self, task: dict) -> dict:
        """PUT /task требует ПОЛНЫЙ объект задачи (get_task → мутация → update_task)."""
        return await self._request("PUT", ep.TASK, json_body=task)

    async def delete_task(self, task_id: int) -> Any:
        return await self._request("DELETE", ep.TASK_BY_ID.format(task_id=task_id))

    async def list_priorities(self) -> list:
        return await self._request("GET", ep.TASK_PRIORITY)

    # ---------- Мои задачи / глобальные списки ----------

    async def list_deadline_tasks(self, workspace_id: int, user_id: int,
                                  with_deadline: bool = True, search: str = "") -> Any:
        """Задачи пространства с дедлайнами (ежедневник) или без них."""
        path = (ep.TASKS_WITH_DEADLINE if with_deadline else ep.TASKS_WITHOUT_DEADLINE).format(
            workspace_id=workspace_id, user_id=user_id)
        return await self._request("GET", path, params={"searchText": search, "sort": ""})

    # ---------- Копирование / перенос / экспорт ----------

    async def copy_task(self, task_id: int, target_project_id: int) -> dict:
        return await self._request("POST", ep.TASK_COPY.format(task_id=task_id),
                                   params={"targetProjectId": target_project_id})

    async def move_task_to_project(self, task_id: int, project_id: int) -> dict:
        return await self._request("PUT", ep.TASK_MOVE_PROJECT.format(task_id=task_id),
                                   params={"projectId": project_id})

    async def export_tasks(self, fmt: str, workspace_id: int, project_id: int,
                           file_name: str) -> bytes:
        """Выгрузка задач проекта в xlsx/csv; возвращает blob."""
        return await self._request("POST", ep.TASK_EXPORT.format(fmt=fmt),
                                   params={"workspaceId": workspace_id,
                                           "projectId": project_id, "fileName": file_name},
                                   _raw=True)

    async def get_task_history(self, task_id: int, page: int = 0, size: int = 20) -> dict:
        return await self._request("GET", ep.TASK_HISTORY.format(task_id=task_id),
                                   params={"page": page, "size": size, "search": "", "filter": "{}"})

    # ---------- Чек-листы ----------

    async def list_checklist(self, task_id: int) -> dict:
        return await self._request("GET", ep.CHECKLIST_LIST.format(task_id=task_id),
                                   params={"page": 0, "size": 9999, "searchText": ""})

    async def add_checklist_item(self, task_id: int, title_html: str, order_num: int = 1) -> dict:
        """title_html — готовый HTML (tools/_shared.render_html)."""
        return await self._request("POST", ep.CHECKLIST,
                                   json_body=bodies.checklist_body(task_id, title_html, order_num))

    async def mark_checklist_item(self, item_id: int, task_id: int, checked: bool) -> dict:
        # Коварность API: returnValue = СТАРОЕ значение чекбокса, сервер инвертирует его
        return await self._request("POST", ep.CHECKLIST_MARK.format(item_id=item_id), json_body={
            "itemId": item_id, "taskId": task_id, "returnValue": not checked,
        })

    async def get_checklist_item(self, task_id: int, item_id: int) -> dict:
        result = await self.list_checklist(task_id)
        for item in result.get("content", []):
            if item.get("id") == item_id:
                return item
        raise NotFoundError(f"Пункт чек-листа {item_id} не найден в задаче {task_id}")

    async def update_checklist_item(self, item: dict) -> dict:
        """PUT /checklist — как и PUT /task, требует ПОЛНЫЙ объект пункта."""
        return await self._request("PUT", ep.CHECKLIST, json_body=item)

    async def delete_checklist_item(self, item_id: int) -> Any:
        return await self._request("DELETE", ep.CHECKLIST_ITEM.format(item_id=item_id))

    # ---------- Комментарии ----------

    async def list_comments(self, task_id: int, page: int = 0, size: int = 20) -> dict:
        return await self._request("GET", ep.COMMENT_LIST.format(task_id=task_id),
                                   params={"page": page, "size": size, "search": "", "filter": "{}"})

    async def add_comment(self, task_id: int, creator_id: int, text_html: str, reply_to: int | None = None) -> dict:
        """text_html — готовый HTML (tools/_shared.render_html)."""
        return await self._request("POST", ep.COMMENT,
                                   json_body=bodies.comment_body(task_id, creator_id, text_html, reply_to))

    async def get_comment(self, task_id: int, comment_id: int) -> dict:
        result = await self.list_comments(task_id, size=9999)
        for c in result.get("content", []):
            if c.get("id") == comment_id:
                return c
        raise NotFoundError(f"Комментарий {comment_id} не найден в задаче {task_id}")

    async def update_comment(self, comment: dict) -> dict:
        """PUT /comment — полный объект комментария."""
        return await self._request("PUT", ep.COMMENT, json_body=comment)

    async def delete_comment(self, comment_id: int) -> Any:
        return await self._request("DELETE", ep.COMMENT_ITEM.format(comment_id=comment_id))

    # ---------- Пользователи ----------

    async def get_my_profile(self) -> dict:
        result = await self._request("GET", ep.USER_PROFILE)
        if isinstance(result, list):  # API возвращает массив с одним элементом
            if not result:
                raise AuthError("Профиль не получен: пустой ответ /userProfile — проверьте токен")
            return result[0]
        return result

    async def find_user_by_email(self, email: str) -> list:
        return await self._request("GET", ep.USER_PROFILE_FIND.format(email=quote(email, safe="")))

    # ---------- Уведомления ----------

    async def list_notifications(self, page: int = 1, size: int = 20) -> dict:
        return await self._request("GET", ep.NOTIFICATIONS, params={"page": page, "size": size, "search": ""})

    async def ack_notifications(self) -> Any:
        """Отметить все уведомления прочитанными."""
        return await self._request("POST", ep.NOTIFICATIONS_ACK)

    # ---------- Вложения ----------

    async def list_attachments(self, task_id: int) -> Any:
        return await self._request("GET", ep.ATTACHMENT_LIST, params={"taskId": task_id})

    async def upload_attachment(self, entity: str, entity_id: int, file_path: str) -> Any:
        """Приложить файл (multipart). entity: 'task' (пока только задачи)."""
        import mimetypes
        from pathlib import Path
        path = Path(file_path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as fh:
            return await self._request(
                "POST", ep.ATTACHER_CREATE.format(entity=entity),
                params={"id": entity_id},
                data={"id": str(entity_id)},
                files={"file": (path.name, fh, mime)},
            )

    async def download_attachment(self, entity: str, entity_id: int, file_name: str) -> bytes:
        return await self._request("POST", ep.ATTACHER_DOWNLOAD.format(entity=entity),
                                   json_body={"fileName": file_name, "id": entity_id},
                                   _raw=True)

    async def delete_attachment(self, attachment_id: int) -> Any:
        return await self._request("DELETE", ep.ATTACHER_ITEM.format(attachment_id=attachment_id))

    # ---------- утилиты ----------

    @staticmethod
    def _json_str(value: str) -> str:
        import json as _json
        return _json.dumps(value)  # generateMCode ждёт JSON-строку "Название"
