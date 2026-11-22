"""Тесты новых фич: мои задачи, копирование/перенос, экспорт, вложения, ack, повтор."""

from __future__ import annotations

import json

import respx
from fastmcp import Client

from yozhka_mcp import server

BASE = "https://yozhka.lukit.ru/backend"


def _data(result):
    data = getattr(result, "data", None)
    if data is None:
        return json.loads(result.content[0].text)
    return data


@respx.mock
async def test_list_my_tasks():
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 17160}])
    route = respx.get(f"{BASE}/userProfile/17160/assignedTasks").respond(json=[
        {"id": 1, "code": "A-1"}, {"id": 2, "code": "B-2"}])
    async with Client(server.mcp) as c:
        result = await c.call_tool("list_my_tasks", {})
        assert len(_data(result)) == 2
        assert route.called


@respx.mock
async def test_list_deadline_tasks_switches_endpoint():
    respx.get(f"{BASE}/userProfile").respond(json=[{"id": 17160}])
    with_dl = respx.get(f"{BASE}/task/18122/allTaskWDeadline/17160").respond(json=[])
    without_dl = respx.get(f"{BASE}/task/18122/allTasksWoDeadline/17160").respond(json=[])
    async with Client(server.mcp) as c:
        await c.call_tool("list_deadline_tasks", {"workspace_id": 18122, "with_deadline": True})
        assert with_dl.called and not without_dl.called
        await c.call_tool("list_deadline_tasks", {"workspace_id": 18122, "with_deadline": False})
        assert without_dl.called


@respx.mock
async def test_copy_and_move_task():
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 10, "code": "X-1", "title": "T"})
    copy_route = respx.post(f"{BASE}/v2/task/copy/10").respond(json={"id": 11, "code": "X-2"})
    move_route = respx.put(f"{BASE}/v2/task/move/10").respond(json={"id": 10, "code": "Y-1"})
    async with Client(server.mcp) as c:
        r = await c.call_tool("copy_task", {"task_code": "X-1", "target_project_id": 55})
        assert _data(r)["code"] == "X-2"
        assert "targetProjectId=55" in str(copy_route.calls.last.request.url)
        r = await c.call_tool("move_task_to_project", {"task_code": "X-1", "project_id": 66})
        assert _data(r)["code"] == "Y-1"
        assert "projectId=66" in str(move_route.calls.last.request.url)


@respx.mock
async def test_export_tasks_writes_file(tmp_path):
    respx.post(f"{BASE}/task/export/xlsx").respond(content=b"PK\x03\x04fake-xlsx")
    async with Client(server.mcp) as c:
        r = await c.call_tool("export_tasks", {
            "workspace_id": 18122, "project_id": 25072, "save_dir": str(tmp_path)})
        data = _data(r)
        assert data["size"] > 0
        assert data["path"].endswith(".xlsx")
        import pathlib
        assert pathlib.Path(data["path"]).read_bytes().startswith(b"PK")


@respx.mock
async def test_ack_notifications():
    route = respx.post(f"{BASE}/notifications/ack").respond(json={})
    async with Client(server.mcp) as c:
        await c.call_tool("ack_notifications", {})
        assert route.called


@respx.mock
async def test_set_task_repeat_body():
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 10, "code": "X-1", "title": "T", "statusId": 2,
        "repeatSetting": {"id": 3, "taskId": 10, "enabled": False, "type": "COPY",
                          "period": "DAILY", "workdaysOnly": True,
                          "daysOfWeek": {"monday": False},
                          "customValue": 1, "customPeriod": "DAY", "anchorDay": 1}})
    route = respx.put(f"{BASE}/task").respond(json={"id": 10, "code": "X-1"})
    async with Client(server.mcp) as c:
        r = await c.call_tool("set_task_repeat", {
            "task_code": "X-1", "enabled": True, "period": "weekly",
            "days_of_week": ["monday", "friday"]})
        body = json.loads(route.calls.last.request.content)
        rs = body["repeatSetting"]
        assert rs["enabled"] is True
        assert rs["period"] == "WEEKLY"  # нормализовано
        assert rs["daysOfWeek"]["monday"] is True
        assert rs["daysOfWeek"]["friday"] is True
        assert rs["daysOfWeek"]["tuesday"] is False
        assert rs["id"] == 3  # существующий объект сохранён (PUT полный)


@respx.mock
async def test_upload_attachment_multipart(tmp_path):
    import pathlib
    f = tmp_path / "report.txt"
    f.write_text("данные")
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 10, "code": "X-1", "title": "T"})
    route = respx.post(f"{BASE}/attacher/task/create").respond(json={"id": 77})
    async with Client(server.mcp) as c:
        await c.call_tool("upload_attachment", {"task_code": "X-1", "file_path": str(f)})
        request = route.calls.last.request
        assert "multipart/form-data" in request.headers["content-type"]
        assert b"report.txt" in request.content


@respx.mock
async def test_download_attachment(tmp_path):
    respx.get(f"{BASE}/task/code/X-1").respond(json={"id": 10, "code": "X-1", "title": "T"})
    respx.post(f"{BASE}/attacher/task/download").respond(content=b"file-bytes")
    async with Client(server.mcp) as c:
        r = await c.call_tool("download_attachment", {
            "task_code": "X-1", "file_name": "../evil.txt", "save_dir": str(tmp_path)})
        data = _data(r)
        # basename-санитизация: ../ не вылезает за каталог
        assert "../" not in data["path"]
        assert data["size"] == len(b"file-bytes")


@respx.mock
async def test_observers_put_full_object():
    respx.get(f"{BASE}/task/code/X-1").respond(json={
        "id": 10, "code": "X-1", "title": "T", "statusId": 2, "observersIds": []})
    route = respx.put(f"{BASE}/task").respond(json={
        "id": 10, "code": "X-1", "observersIds": [17160]})
    async with Client(server.mcp) as c:
        r = await c.call_tool("set_task_observers", {"task_code": "X-1", "user_ids": [17160]})
        body = json.loads(route.calls.last.request.content)
        assert body["observersIds"] == [17160]
        assert body["id"] == 10
        assert _data(r)["observersIds"] == [17160]
