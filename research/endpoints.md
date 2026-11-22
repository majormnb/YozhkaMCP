# Реверс API Ёжки (yozhka.lukit.ru) — полный каталог эндпоинтов

Дата: 2026-11-22. Источник: живая сессия в браузере (перехват fetch/XHR), аккаунт begattsu@gmail.com.
Base URL: `https://yozhka.lukit.ru/backend`
Auth: `Authorization: Bearer <accessToken>` (Keycloak, realm `bun`, `https://yozhka.lukit.ru/auth/realms/bun`).
Токены: `ejka.accessToken` (RS256, ~1 час), `ejka.refreshToken` (~30 дней) в localStorage.

Сырые дампы: `api-capture/capture-1..4*.json` (токены замаскированы).

## Соглашения

- Пагинация: `?page=&size=` (workspace/project с 1, task/checklist с 0), ответ `{content, totalPages, pageNumber, elementsOnPage, totalElements}`.
- «Пустая вечность» = `2999-12-31T00:00:00Z` (deadlineTs, closeTs).
- Тексты — HTML (`<p>…</p>`): `contentData` (описание задачи), `itemTitle` (чек-лист), `contentComment` (комментарий).
- Пермиссии в объектах: `userWorkspaceAuthorities[]`, `userProjectAuthorities[]`.
- Дедлайн приходит с таймзоной: `2026-11-25T23:59:59+03:00`.

## Auth

| Метод | Путь | Тело | Примечание |
|---|---|---|---|
| POST | `/auth/refresh` | `{refreshToken}` | → `{accessToken, refreshToken, ...}` — refresh-токен живёт ~30 дней, основной способ аутентификации для MCP |
| GET | `/auth/me` | — | текущий юзер (из бандла) |

## Workspaces

| Метод | Путь | Тело/параметры |
|---|---|---|
| POST | `/workspace/generateMCode` | body: JSON-строка `"Название"` → `"CODE"` |
| POST | `/workspace` | `{title, code, description, iconColor}` |
| GET | `/workspace/my?page=1&size=24&currentWorkspaceId=` | мои пространства |
| GET | `/workspace/{code}` | детали + subscription + authorities |
| PUT | `/workspace` | полный объект (rename/description/icon) |
| DELETE | `/workspace/...` | UI: «Удалить пространство» (не снимали) |
| GET | `/workspace/{id}/users` | участники (приглашённые: `id:null`) |
| POST | `/workspaces/{id}/addUsers` | `{mails:[email], roleId}` ← ВНИМАНИЕ: `workspaces` во мн.ч.! |
| GET | `/workspace/role/list` | Владелец(17)/Администратор(18)/Участник(16) |
| GET | `/workspaceSubscription/{id}/limits` | лимиты |
| GET | `/workspaceSubscription/subscriptionType/list` | тарифы |
| GET | `/workspaceTag/{workspaceId}?page=0&size=999&search=` | метки |
| POST | `/workspaceTag` | `{tagName, workspaceId, backgroundColor}` |
| DELETE | `/workspaceTag/...` | (UI: удаление метки; не снимали) |

## Projects

| Метод | Путь | Тело/параметры |
|---|---|---|
| POST | `/project/generateMCode?projectName=&workspaceId=` | → `"CODE"` |
| POST | `/project` | `{workspaceId, title, code, iconColor, iconName, iconUrl}` |
| GET | `/project/tiles/my?page=1&size=24&workspaceId=&stateFilter={"active":true}` | stateFilter: active/favorite/archive/blocked |
| GET | `/project/titles/my?...` | компактный список |
| GET | `/project/code/{code}/{workspaceId}` | детали |
| GET | `/project/{id}/{workspaceId}` | детали |
| PUT | `/project` | полный объект |
| POST | `/project/updateProjectState?workspaceId=&projectId=&targetProjectStateId=` | 1=active, 2=archive |
| POST | `/project/favorites/{projectId}` | toggle избранного |
| GET | `/project/{id}/users` / `/project/{id}/activeUsers` | участники проекта |
| GET | `/projectUserSettings/{projectId}` | настройки вида |
| DELETE | `/project/...` | UI: меню проекта → Удалить (не снимали) |

## Канбан-колонки (статусы)

| Метод | Путь | Тело |
|---|---|---|
| GET | `/workflowStatusesAvail?projectId=` | дефолт: 1 Новая, 2 В работе, 3 Закрыта, 4 В ожидании + кастом |
| POST | `/workflowStatusesAvail` | `{projectId, statusName, statusColor}` → `{taskStatusId, orderNum}` |
| PUT | `/workflowStatusesAvail` | `{projectId, taskStatusId, statusName, statusColor}` |
| DELETE | `/workflowStatusesAvail` | `{projectId, taskStatusId}` |

## Tasks

| Метод | Путь | Тело/параметры |
|---|---|---|
| POST | `/task?onTop=true` | `{title, projectId, priorityId, statusId, typeId:2, hierarchyLevelId:2, ...}` |
| GET | `/task/{projectId}/list?page=0&size=9999&searchText=` | список задач проекта |
| GET | `/task/searchByProjectId/{projectId}?page=0&size=9999&searchText=` | поиск |
| GET | `/task/code/{taskCode}` | детали (BMCPTESTX-1) |
| PUT | `/task` | ПОЛНЫЙ объект: title, contentData, priorityId, statusId (=move), deadlineTs, executorsIds, observersIds, tags[] |
| DELETE | `/task/{taskId}` | удаление |
| GET | `/taskPriority` | 0..4 (Не задан..Критичный) |
| GET | `/task/{taskId}/history?page=0&size=20&search=&filter={}` | история изменений |
| POST | `/userTaskViewHistory` | `{workspaceId, taskId, userId}` |

## Чек-листы

| Метод | Путь | Тело |
|---|---|---|
| GET | `/checklist/{taskId}/list?page=0&size=9999&searchText=` | |
| POST | `/checklist` | `{taskId, itemTitle:"<p>…</p>", orderNum, ...}` |
| POST | `/checklist/mark/{itemId}` | `{itemId, taskId, returnValue}` → itemChecked, markBy, markTs |

## Комментарии

| Метод | Путь | Тело |
|---|---|---|
| GET | `/comment/{taskId}/list?page=0&size=20&search=&filter={}` | |
| POST | `/comment` | `{contentComment:"<p>…</p>", creatorId, replyTo, taskId, attachments[]}` |
| GET | `/userProfile/usersComment?taskId=` | комментаторы |

## Пользователи

| Метод | Путь | Примечание |
|---|---|---|
| GET | `/userProfile` | мой профиль |
| GET | `/userProfile/find/{email}` | поиск по email (пустой [] = нет такого) |
| GET | `/userProfile/usersChangesHistory?taskId=` | авторы изменений |

## Уведомления

| Метод | Путь |
|---|---|
| GET | `/notifications?page=1&size=20&search=` → `{unreadCount, notifications[]}` |

## Схемы (ключевые поля)

**Workspace:** id, title, code, description, companyId, creatorId, creatorFullName, createTs, closeTs, iconColor, iconUrl, userWorkspaceAuthorities[], subscription{}.

**Project:** id, title, code, createTs, closeTs, projectStatusId, projectStateId (1 active/2 archive), ownerId, ownerFullName, iconUrl, iconColor, iconName, userProjectRoles[], userProjectAuthorities[], isFavorite, description, updateTs, workspaceId, isBlocked.

**Task:** id, title, projectId, creatorId, statusId, typeId, createTs, updateTs, code, closeTs, parentId, priorityId, hierarchyLevelId, orderNum, executorsIds[], observersIds[], contentData, contentDataWithTags, deadlineTs, deadlineClTs, deadlineMarked, taskNum, attachments[], tags[], checkLists[], isCompleted, completeTs, workspaceCode, projectCode, projectTitle, statusColor, statusName, repeatSetting{}.

**ChecklistItem:** id, taskId, orderNum, itemTitle (HTML), itemAuthor, createTs, updateTs, markBy, markTs, markComment, itemChecked, deadlineClTs, totalItemsCheckLists, executorsIds[].

**Comment:** id, taskId, contentComment (HTML), contentCommentWithTags, creatorId, createTs, updateTs, replyTo, closeTs, attachments[], attachIsPending.

**WorkspaceTag:** id, tagName, workspaceId, backgroundColor.

**WorkflowStatus:** id, workflowId, orderNum, taskStatusId, statusColor (+ name из справочника статусов).

**Authorities:** workspace: `workspace.read|update|delete`, `workspace.subscription.*`, `workspace.invoice.*`, `workspace.payway.*`, `workspace.team_role.read|create|delete|update|set_owner`, `workspace.project.read|create|update|delete|update_state`, `workspace.tag.read|create|delete`; project: `authority_ref.project.add_participant|archive|edit|info|read`, `authority_ref.task.create|delete|move`, `authority_ref.task_status.create|delete|update`.

## Не снято (мелочи, не блокируют MCP)

- DELETE /workspace, DELETE /project (UI подтверждает кодом; паттерн очевиден: DELETE /{entity}/{id})
- DELETE /workspaceTag, PUT /comment (меню комментария)
- Вложения (attacher: /getAttachment/list, /backend/attacher/*)
- Экспорт задач («Выгрузить задачи»)
- «Создать копию»/«Переместить задачу» (меню задачи)
