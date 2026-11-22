# Реверс API Ёжки (yozhka.lukit.ru) — каталог эндпоинтов

Дата: 2026-11-22. Источник: живая сессия в браузере (perехват fetch/XHR), аккаунт begattsu@gmail.com.
Base URL: `https://yozhka.lukit.ru/backend`
Auth: `Authorization: Bearer <accessToken>` (Keycloak, realm `bun`).
Токены: `ejka.accessToken` (RS256, ~1 час), `ejka.refreshToken` (~30 дней) в localStorage.
Keycloak: `https://yozhka.lukit.ru/auth/realms/bun`

Сырые дампы: `api-capture/capture-1-projects-tasks.json`, `api-capture/capture-2-workspace-project.json`.

## Соглашения

- Пагинация: `?page=1&size=24` (у `/task/*` — `page=0`), ответ `{content: [...], totalPages, pageNumber, elementsOnPage, totalElements}`.
- «Пустая вечность» = `2999-12-31T00:00:00Z` (deadlineTs, closeTs).
- Тексты описаний/чек-листов — HTML (`<p>...</p>`), поля `contentData`, `itemTitle`.
- Пермиссии приходят в объектах: `userWorkspaceAuthorities[]`, `userProjectAuthorities[]` — имена вида `workspace.update`, `authority_ref.task.move`.

## Workspaces (пространства)

| Метод | Путь | Тело / параметры | Ответ | Примечание |
|---|---|---|---|---|
| POST | `/workspace/generateMCode` | JSON-строка `"MCP Test"` | `"BMCPTESTX"` (plain string) | код по названию |
| POST | `/workspace` | `{title, code, description, iconColor}` | Workspace | создание |
| GET | `/workspace/my?page=1&size=24&currentWorkspaceId=` | — | `{content: [Workspace]}` | мои пространства |
| GET | `/workspace/{code}` | — | Workspace (+ `subscription`, `userWorkspaceAuthorities`) | детали |
| PUT | `/workspace` | полный объект Workspace | Workspace | переименование/описание/иконка |
| GET | `/workspace/{id}/users` | — | [User] | участники |
| GET | `/workspace/role/list` | — | [{roleId, roleType, roleName, roleNameM}] | Владелец(17,workspace_owner), Администратор(18), Участник(16) |
| GET | `/workspaceSubscription/{id}/limits` | — | `{subscriptionSettings{...}, workspaceTeamTotal, workspaceProjectsTotal, workspaceAttachmentTotal}` | лимиты тарифа |
| GET | `/workspaceSubscription/subscriptionType/list` | — | [SubscriptionType] | Базовый/PRO + функциональность |
| GET | `/workspaceAnnouncement/{id}` | — | [] | анонсы |
| GET | `/workspaceTag/{workspaceId}?page=0&size=999` | — | `{content: [Tag]}` | метки пространства |

Workspace: `{id, title, code, description, companyId, creatorId, creatorFullName, createTs, closeTs, iconColor, iconUrl, userWorkspaceAuthorities[], subscription{...}}`

Authorities workspace: `workspace.read|update|delete`, `workspace.subscription.*`, `workspace.invoice.*`, `workspace.payway.*`, `workspace.team_role.read|create|delete|update|set_owner`, `workspace.project.read|create|update|delete|update_state`, `workspace.tag.read|create|delete`.

Удаление пространства: кнопка в UI «Удалить пространство» (DELETE /workspace/{...} — запрос не снимали, UI подтверждение).

## Projects (проекты)

| Метод | Путь | Тело / параметры | Ответ | Примечание |
|---|---|---|---|---|
| POST | `/project/generateMCode?projectName=&workspaceId=` | — | `"REVENG"` | код по названию |
| POST | `/project` | `{workspaceId, title, code, iconColor, iconName, iconUrl}` | Project | создание |
| GET | `/project/tiles/my?page=1&size=24&workspaceId=&stateFilter={"active":true,...}` | stateFilter: active/favorite/archive/blocked (URL-encoded JSON) | `{content: [Project]}` | плитки |
| GET | `/project/titles/my?page=1&size=24&workspaceCode=&workspaceId=&currentProjectId=&blocked=true` | — | `{content: [{id, iconUrl, iconColor, title, code, isFavorite, workspaceId}]}` | компактный список |
| GET | `/project/code/{code}/{workspaceId}` | — | Project | детали по коду |
| GET | `/project/{id}/{workspaceId}` | — | Project | детали по id |
| PUT | `/project` | полный объект Project | Project | rename/описание/иконка |
| POST | `/project/updateProjectState?workspaceId=&projectId=&targetProjectStateId=` | — | `{}` | state: 1=активный, 2=архив |
| POST | `/project/favorites/{projectId}` | — | пусто | toggle избранного |
| GET | `/project/{id}/users` | — | [User] | все участники |
| GET | `/project/{id}/activeUsers` | — | [User] | активные |
| POST | `/project/{id}/addUsers` | (UI не снят) | — | добавить участников |
| POST | `/project/{id}/deleteUser` | (UI не снят) | — | удалить участника |
| GET | `/project/role` | — | роли проекта | (из бандла) |
| GET | `/projectUserSettings/{projectId}` | — | `{projectId, userId, style{...}, isFavorite, tasksFilter, tasksSort, ...}` | пользовательские настройки вида |

Project: `{id, title, code, createTs, closeTs, projectStatusId, projectStateId, ownerId, ownerFullName, iconUrl, iconColor, iconName, userProjectRoles[], userProjectAuthorities[], isFavorite, description, updateTs, workspaceId, isBlocked}`

Authorities project: `authority_ref.project.add_participant|archive|edit|info|read`, `authority_ref.task.create|delete|move`, `authority_ref.task_status.create|delete|update`.

## Workflow / колонки (статусы задач)

| Метод | Путь | Тело | Примечание |
|---|---|---|---|
| GET | `/workflowStatusesAvail?projectId=` | — | дефолт+кастом: [{id, name, nameM, closeTs, orderNum, statusColor}]. Дефолты: 1 Новая, 2 В работе, 3 Закрыта, 4 В ожидании |
| PUT | `/workflowStatusesAvail` | `{projectId, taskStatusId, statusName, statusColor}` | переопределить имя/цвет колонки → `{id, workflowId, orderNum, taskStatusId(кастомный), statusColor}` |
| POST | `/workflowStatusesAvail` | (UI не снят) | создание колонки (кнопка «+» на доске) |
| DELETE | `/workflowStatusesAvail` | (UI не снят) | «Удалить столбец» |

## Tasks (бонусом, снято в первой сессии)

| Метод | Путь | Примечание |
|---|---|---|
| GET | `/task/{projectId}/list?page=0&size=9999&searchText=` | `{content: [Task]}` |
| GET | `/task/code/{taskCode}` | детали по коду BMCPTESTX-1 |
| POST | `/task?onTop=true` | создание: `{title, projectId, priorityId, statusId, typeId:2, hierarchyLevelId:2, contentData, ...}` |
| PUT | `/task` | полный объект Task: переименование, описание (contentData HTML), priorityId, statusId (move!), deadlineTs, executorsIds, observersIds, tags[] |
| GET | `/taskPriority` | 0 не задан, 1 низкий, 2 средний, 3 высокий, 4 критичный |
| GET | `/checklist/{taskId}/list?page=0&size=9999&searchText=` | чек-листы |
| POST | `/checklist` | `{taskId, itemTitle:"<p>...</p>", orderNum, ...}` |
| GET | `/comment/{taskId}/list?page=0&size=20&search=&filter={}` | комментарии |
| POST | `/userTaskViewHistory` | `{workspaceId, taskId, userId}` |
| GET | `/userProfile` | мой профиль |
| GET | `/userProfile/usersComment?taskId=` | комментаторы задачи |

Task: `{id, title, projectId, creatorId, statusId, typeId, createTs, updateTs, code, closeTs, parentId, priorityId, hierarchyLevelId, orderNum, executorsIds, observersIds, contentData, contentDataWithTags, deadlineTs, deadlineClTs, deadlineMarked, taskNum, attachments[], tags[], checkLists[], isCompleted, completeTs, workspaceCode, projectCode, projectTitle, statusColor, statusName, repeatSetting{...}}`

## Что осталось снять (следующая сессия)

- POST `/workspace` приглашение участника (email + roleId) — END /workspace/{id}/users или team-эндпоинт
- POST/DELETE `/project/{id}/addUsers` / `deleteUser` — точные тела
- POST/DELETE `/workflowStatusesAvail` — создание/удаление колонок
- DELETE `/project`, DELETE `/workspace` — удаление (UI подтверждает кодом)
- Комментарий: POST `/comment`
- Метки: POST/DELETE `/workspaceTag`
- Поиск: `/project/search/{query}`, глобальный поиск
- Вложения (attacher)
- Экспорт задач («Выгрузить задачи»)
