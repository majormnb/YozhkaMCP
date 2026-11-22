"""Тулы: вложения задач (attacher)."""

from __future__ import annotations

from pathlib import Path

from fastmcp import FastMCP

from ..api.client import YozhkaClient
from ._shared import run, write_guard


def register(mcp: FastMCP, client: YozhkaClient, read_only: bool) -> None:

    @mcp.tool
    async def list_attachments(task_code: str) -> list:
        """[read-only] Вложения задачи: [{id, fileName, fileSize, …}]."""
        task = await client.get_task(task_code)
        return await client.list_attachments(task["id"])

    @mcp.tool
    async def download_attachment(task_code: str, file_name: str,
                                  save_dir: str | None = None) -> dict:
        """[read-only] Скачать вложение задачи в файл; вернуть {path, size}.
        save_dir не указан — системная временная папка."""
        import tempfile
        task = await client.get_task(task_code)
        data = await client.download_attachment("task", task["id"], file_name)
        directory = Path(save_dir) if save_dir else Path(tempfile.gettempdir())
        directory.mkdir(parents=True, exist_ok=True)
        # basename — чтобы имя с сервера не вылезло за пределы каталога
        path = directory / Path(file_name).name
        path.write_bytes(data)
        return {"path": str(path), "size": len(data)}

    @mcp.tool
    async def upload_attachment(task_code: str, file_path: str) -> dict:
        """[write] Приложить локальный файл к задаче (путь к файлу на машине MCP-сервера)."""
        async def _fn():
            if not Path(file_path).is_file():
                from fastmcp.exceptions import ToolError
                raise ToolError(f"Файл не найден: {file_path}")
            task = await client.get_task(task_code)
            return await client.upload_attachment("task", task["id"], file_path)
        return await run(write_guard(read_only, _fn))

    @mcp.tool
    async def delete_attachment(attachment_id: int) -> dict:
        """[write] Удалить вложение (id из list_attachments)."""
        async def _fn():
            await client.delete_attachment(attachment_id)
            return {"deleted": attachment_id}
        return await run(write_guard(read_only, _fn))
