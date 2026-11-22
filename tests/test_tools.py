"""In-memory тесты MCP-тулов (fastmcp.Client без процесса)."""

from __future__ import annotations

import json

import respx
from fastmcp import Client

from yozhka_mcp import server

BASE = "https://yozhka.lukit.ru/backend"


@respx.mock
async def test_list_workspaces_tool():
    respx.get(f"{BASE}/workspace/my").respond(json={
        "content": [{"id": 18122, "title": "MCP Test", "code": "BMCPTESTX"}],
        "totalElements": 1,
    })
    async with Client(server.mcp) as client:
        result = await client.call_tool("list_workspaces", {})
        data = result.data if hasattr(result, "data") else json.loads(result.content[0].text)
        assert data["content"][0]["code"] == "BMCPTESTX"


@respx.mock
async def test_get_task_strips_html_description():
    respx.get(f"{BASE}/task/code/BMCPTESTX-1").respond(json={
        "id": 215578, "code": "BMCPTESTX-1", "title": "T",
        "contentData": "<p>Описание</p>", "statusId": 2,
    })
    async with Client(server.mcp) as client:
        result = await client.call_tool("get_task", {"task_code": "BMCPTESTX-1"})
        data = result.data if hasattr(result, "data") else json.loads(result.content[0].text)
        assert data["description"] == "Описание"


@respx.mock
async def test_move_task_puts_full_object():
    get_route = respx.get(f"{BASE}/task/code/BMCPTESTX-1").respond(json={
        "id": 215578, "code": "BMCPTESTX-1", "title": "T", "statusId": 1,
        "projectId": 25072, "priorityId": 2,
    })
    put_route = respx.put(f"{BASE}/task").respond(json={
        "id": 215578, "code": "BMCPTESTX-1", "title": "T", "statusId": 3,
    })
    async with Client(server.mcp) as client:
        await client.call_tool("move_task", {"task_code": "BMCPTESTX-1", "status_id": 3})
        assert get_route.called
        body = json.loads(put_route.calls.last.request.content)
        assert body["statusId"] == 3
        assert body["id"] == 215578  # полный объект
