# yozhka-mcp

Неофициальный [MCP](https://modelcontextprotocol.io)-сервер для [Ёжки](https://yozhka.lukit.ru/) — бесплатного канбан-планировщика от Лукит.

Позволяет AI-ассистенту (Claude, Cursor, ZCode, OpenCode и др.) работать с твоими пространствами, проектами и задачами: создавать, двигать, комментировать, назначать исполнителей, управлять колонками и участниками.

> ⚠️ У Ёжки нет публичного API — сервер работает через внутренний REST API веб-приложения (`yozhka.lukit.ru/backend`), реверс-инжиниринг от 2026-11-22. API может измениться без предупреждения; всё API-специфичное изолировано в `src/yozhka_mcp/api/endpoints.py`. Для личного использования.

## Возможности (44 тула)

- **Пространства**: список, детали, создание, переименование, участники, приглашения по email, роли, лимиты тарифа
- **Проекты**: список (активные/избранные/архив), детали, создание, переименование, архив/восстановление, избранное, участники
- **Канбан-колонки**: список, создание, переименование, смена цвета, удаление
- **Задачи**: список/поиск, детали, создание, редактирование, перемещение между колонками, приоритет, дедлайн, исполнители, метки, отметка выполнения, удаление, история изменений
- **Чек-листы**: пункты, отметки
- **Комментарии**: список, добавление
- **Пользователи**: профиль, поиск по email; **Уведомления**
- **Пермиссии**: полномочия (`userWorkspaceAuthorities` / `userProjectAuthorities`) приходят в объектах — read/write доступ виден напрямую

Read/write управляется переменной `YOZHKA_READ_ONLY` (см. ниже).

## Установка

Нужен Python 3.11+ и [uv](https://docs.astral.sh/uv/):

```bash
git clone <repo> ~/yozhka-mcp && cd ~/yozhka-mcp
uv sync
```

## Как достать токен

Ёжка использует Keycloak SSO. MCP-серверу нужен **refresh-токен** (живёт ~30 дней):

1. Открой https://yozhka.lukit.ru в браузере и войди.
2. DevTools (F12) → Console:
   ```js
   copy(JSON.parse(localStorage.getItem('ejka.refreshToken')))
   ```
   (токен скопируется в буфер обмена)
3. Положи его в `~/yozhka-mcp/.env`:
   ```
   YOZHKA_REFRESH_TOKEN=eyJhbGciOiJIUzUxMiIs...
   ```
4. Через ~30 дней сессия истечёт — повтори шаги (сервер сам обновляет access-токен через `/auth/refresh`).

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `YOZHKA_REFRESH_TOKEN` | — | refresh-токен (~30 дней), основной способ |
| `YOZHKA_ACCESS_TOKEN` | — | готовый access-токен (~1 час), альтернатива |
| `YOZHKA_BASE_URL` | `https://yozhka.lukit.ru/backend` | base URL API |
| `YOZHKA_READ_ONLY` | `false` | `true` — write-тулы не регистрируются + guard на вызов |
| `YOZHKA_TIMEOUT` | `30` | таймаут запроса, сек |
| `YOZHKA_DEBUG` | `false` | debug-логи |

## Подключение

### ZCode

В конфиг MCP-серверов ZCode:

```json
{
  "mcpServers": {
    "yozhka": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/ТВОЙ_ЮЗЕР/yozhka-mcp", "yozhka-mcp"],
      "env": {
        "YOZHKA_REFRESH_TOKEN": "eyJ...",
        "YOZHKA_READ_ONLY": "false"
      }
    }
  }
}
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yozhka": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/ТВОЙ_ЮЗЕР/yozhka-mcp", "yozhka-mcp"],
      "env": { "YOZHKA_REFRESH_TOKEN": "eyJ..." }
    }
  }
}
```

### Cursor

`.cursor/mcp.json` в проекте (или глобально `~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "yozhka": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/ТВОЙ_ЮЗЕР/yozhka-mcp", "yozhka-mcp"],
      "env": { "YOZHKA_REFRESH_TOKEN": "eyJ..." }
    }
  }
}
```

### OpenCode

`opencode.json`:

```json
{
  "mcp": {
    "yozhka": {
      "type": "local",
      "command": ["uv", "run", "--directory", "/Users/ТВОЙ_ЮЗЕР/yozhka-mcp", "yozhka-mcp"],
      "environment": {
        "YOZHKA_REFRESH_TOKEN": "eyJ...",
        "YOZHKA_READ_ONLY": "false"
      }
    }
  }
}
```

## Проверка

```bash
# MCP Inspector
uv run mcp dev src/yozhka_mcp/server.py

# или просто тесты
uv run pytest
```

## Структура

```
src/yozhka_mcp/
  server.py             # FastMCP, регистрация тулов, READ_ONLY
  config.py             # env-конфиг
  api/
    client.py           # httpx + Bearer + авто-refresh + tenacity-ретраи
    endpoints.py        # ВСЕ пути API (правится при drift)
    exceptions.py       # AuthError, NotFound, PermissionDenied...
  tools/                # тулы по доменам: workspaces, projects, columns, tasks,
                        # checklists, comments, misc, auth
tests/                  # respx-моки + in-memory fastmcp.Client
research/               # результаты реверса API (endpoints.md, сырые дампы)
```

## Отказ от ответственности

Проект не связан с Лукит/Ростелеком. Использует приватное API; соблюдай пользовательское соглашение сервиса и не злоупотребляй запросами (в клиенте есть ретраи с backoff).

## Лицензия

MIT
