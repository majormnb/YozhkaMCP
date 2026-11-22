"""Поведенческие тесты тулов: честные ошибки, инверсия returnValue, order_num."""

from __future__ import annotations

import json

import respx
from fastmcp import Client
from fastmcp.exceptions import ToolError

from yozhka_mcp import server

BASE = "https://yozhka.lukit.ru/backend"


def _data(result):
    data = getattr(result, "data", None)
    if data is None:
        return json.loads(result.content[0].text)
    return data


def _result_data(result):
    return result.data if hasattr(result, "data") else json.loads(result.content[0].text)


@respx.mock
async def test_unknown_priority_raises_not_silent_default():
    """Раньше неизвестный приоритет молча становился 'Средний'."""
    respx.get(f"{BASE}/taskPriority").respond(json=[
        {"id": 1, "priorityName": "Низкий"}, {"id": 2, "priorityName": "Средний"},
        {"id": 3, "priorityName": "Высокий"},
    ])
    async with Client(server.mcp) as client:
        try:
            await client.call_tool("create_task", {
                "project_id": 1, "title": "T", "priority": "Критичный"})
            raise AssertionError("должен был упасть с ToolError")
        except ToolError as exc:
            assert "Критичный" in str(exc)
            assert "Средний" in str(exc)  # список допустимых в сообщении


@respx.mock
async def test_unknown_status_id_raises():
    """Невалидный status_id не подменяется первой колонкой молча."""
    respx.get(f"{BASE}/workflowStatusesAvail").respond(json=[
        {"id": 1027, "name": "Бэклог", "orderNum": 0},
        {"id": 2, "name": "В работе", "orderNum": 1},
    ])
    async with Client(server.mcp) as client:
        try:
            await client.call_tool("create_task", {
                "project_id": 1, "title": "T", "status_id": 1})
            raise AssertionError("должен был упасть: status_id=1 нет после переименования колонки")
        except ToolError as exc:
            assert "1027" in str(exc)


@respx.mock
async def test_invite_unknown_role_raises():
    respx.get(f"{BASE}/workspace/role/list").respond(json=[
        {"roleId": 16, "roleName": "Участник"}, {"roleId": 17, "roleName": "Администратор"},
    ])
    async with Client(server.mcp) as client:
        try:
            await client.call_tool("invite_workspace_users", {
                "workspace_id": 1, "mails": ["a@b.c"], "role": "Админ"})
            raise AssertionError("должен был упасть с ToolError")
        except ToolError as exc:
            assert "Администратор" in str(exc)


@respx.mock
async def test_unknown_tag_id_raises():
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5})
    respx.get(url=f"{BASE}/workspaceTag/9", params={"page": "0", "size": "999"}
              ).respond(json={"content": [{"id": 33, "tagName": "метка"}], "totalElements": 1})
    async with Client(server.mcp) as client:
        try:
            await client.call_tool("set_task_tags", {
                "task_code": "X-1", "tag_ids": [33, 999], "workspace_id": 9})
            raise AssertionError("должен был упасть: tag_id=999 не существует")
        except ToolError as exc:
            assert "999" in str(exc)


@respx.mock
async def test_mark_checklist_item_sends_inverted_return_value():
    """Коварность API: returnValue = СТАРОЕ значение, сервер его инвертирует."""
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 10, "code": "X-1", "title": "T"})
    route = respx.post(f"{BASE}/checklist/mark/55").respond(json={})
    async with Client(server.mcp) as client:
        await client.call_tool("mark_checklist_item", {
            "task_code": "X-1", "item_id": 55, "checked": True})
        body = json.loads(route.calls.last.request.content)
        assert body["returnValue"] is False  # хотим checked=True -> шлём not True


@respx.mock
async def test_add_checklist_item_order_num_increments():
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 10, "code": "X-1", "title": "T"})
    respx.get(f"{BASE}/checklist/10/list").respond(json={"content": [
        {"id": 1, "orderNum": 1}, {"id": 2, "orderNum": 3}], "totalElements": 2})
    route = respx.post(f"{BASE}/checklist").respond(json={"id": 3})
    async with Client(server.mcp) as client:
        await client.call_tool("add_checklist_item", {"task_code": "X-1", "title": "новый"})
        body = json.loads(route.calls.last.request.content)
        assert body["orderNum"] == 4  # max(1,3)+1, а не константа 1


@respx.mock
async def test_add_comment_escapes_xss_in_payload():
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 10, "code": "X-1", "title": "T"})
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    route = respx.post(f"{BASE}/comment").respond(json={"id": 5})
    async with Client(server.mcp) as client:
        await client.call_tool("add_comment", {
            "task_code": "X-1", "text": '<img src=x onerror="alert(1)">'})
        body = json.loads(route.calls.last.request.content)
        assert "&lt;img" in body["contentComment"]
        assert "<img" not in body["contentComment"]


@respx.mock
async def test_api_error_becomes_readable_tool_error():
    """403 от API доходит клиенту как понятное сообщение, а не замаскированный трейсбек."""
    respx.get(f"{BASE}/task/code/X-1").respond(403, json={
        "status": 403, "message": "Доступ запрещен", "path": "/task/code/X-1"})
    async with Client(server.mcp) as client:
        try:
            await client.call_tool("get_task", {"task_code": "X-1"})
            raise AssertionError("должен был упасть")
        except ToolError as exc:
            assert "403" in str(exc) and "Доступ запрещен" in str(exc)


# ---------- подтверждение опасных действий ----------

@respx.mock
async def test_update_description_of_foreign_task_requires_confirmation():
    """Описание ЧУЖОЙ задачи (creatorId != me) без confirm=True НЕ меняется — вопрос."""
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5,
        "creatorId": 999,  # чужая задача
        "contentData": "<p>старое</p>"})
    put_route = respx.put(f"{BASE}/task").respond(json={"id": 1})
    async with Client(server.mcp) as c:
        r = await c.call_tool("update_task", {
            "task_code": "X-1", "description": "новое описание"})
        data = _data(r)
        assert data["confirmation_required"] is True
        assert "создана другим пользователем" in data["message"]
        assert not put_route.called  # ничего не изменено


@respx.mock
async def test_update_description_of_own_task_no_gate():
    """В СВОЕЙ задаче (creatorId == me) описание меняется без confirm."""
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5,
        "creatorId": 7,  # своя задача
        "contentData": "<p>старое</p>"})
    put_route = respx.put(f"{BASE}/task").respond(json={
        "id": 1, "code": "X-1", "contentData": "<p>новое</p>"})
    async with Client(server.mcp) as c:
        r = await c.call_tool("update_task", {
            "task_code": "X-1", "description": "новое"})
        assert _data(r)["description"] == "новое"
        assert put_route.called


@respx.mock
async def test_update_description_with_confirm_executes():
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    get_route = respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5,
        "creatorId": 999,
        "contentData": "<p>старое</p>"})
    put_route = respx.put(f"{BASE}/task").respond(json={
        "id": 1, "code": "X-1", "contentData": "<p>новое</p>"})
    async with Client(server.mcp) as c:
        r = await c.call_tool("update_task", {
            "task_code": "X-1", "description": "новое", "confirm": True})
        assert _data(r)["description"] == "новое"
        assert put_route.called


@respx.mock
async def test_update_title_of_own_task_no_gate():
    """Переименование СВОЕЙ задачи — без гейта."""
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5, "creatorId": 7})
    put_route = respx.put(f"{BASE}/task").respond(json={"id": 1, "code": "X-1", "title": "Новый"})
    async with Client(server.mcp) as c:
        r = await c.call_tool("update_task", {"task_code": "X-1", "title": "Новый"})
        assert _data(r)["title"] == "Новый"
        assert put_route.called


@respx.mock
async def test_update_title_of_foreign_task_requires_confirmation():
    """Переименование ЧУЖОЙ задачи — гейт, как и описание."""
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5, "creatorId": 999})
    put_route = respx.put(f"{BASE}/task").respond(json={"id": 1})
    async with Client(server.mcp) as c:
        r = await c.call_tool("update_task", {"task_code": "X-1", "title": "Новый"})
        data = _data(r)
        assert data["confirmation_required"] is True
        assert "title" in data["action"]
        assert not put_route.called


@respx.mock
async def test_update_title_and_description_foreign_one_confirm_covers_both():
    """Один confirm=true подтверждает сразу title и description чужой задачи."""
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 7, "displayName": "Я"}])
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "T", "statusId": 2, "projectId": 5,
        "creatorId": 999, "contentData": "<p>старое</p>"})
    put_route = respx.put(f"{BASE}/task").respond(json={
        "id": 1, "code": "X-1", "title": "Новый", "contentData": "<p>новое</p>"})
    async with Client(server.mcp) as c:
        r = await c.call_tool("update_task", {
            "task_code": "X-1", "title": "Новый", "description": "новое", "confirm": True})
        data = _data(r)
        assert data["title"] == "Новый" and data["description"] == "новое"
        assert put_route.called


@respx.mock
async def test_delete_task_requires_confirmation():
    delete_route = respx.delete(f"{BASE}/task/1").respond(json={})
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 1, "code": "X-1", "title": "Важная", "creatorId": 7})
    async with Client(server.mcp) as c:
        r = await c.call_tool("delete_task", {"task_code": "X-1"})
        data = _data(r)
        assert data["confirmation_required"] is True
        assert "УДАЛИТЬ" in data["message"] and "необратимо" in data["message"]
        assert data["task_title"] == "Важная"
        assert not delete_route.called  # задача жива


@respx.mock
async def test_delete_task_with_confirm_executes():
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 1, "code": "X-1", "title": "Важная"})
    delete_route = respx.delete(f"{BASE}/task/1").respond(json={})
    async with Client(server.mcp) as c:
        r = await c.call_tool("delete_task", {"task_code": "X-1", "confirm": True})
        assert _data(r)["deleted"] == "X-1"
        assert delete_route.called
