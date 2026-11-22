# yozhka-mcp

Неофициальный [MCP](https://modelcontextprotocol.io)-сервер для [Ёжки](https://yozhka.lukit.ru/) — бесплатного канбан-планировщика от Лукит. Подключается к AI-ассистенту (ZCode, Claude Desktop, Cursor, OpenCode и любому другому MCP-клиенту) и даёт ему полный доступ к вашим пространствам, проектам и задачам: создавать и двигать задачи, управлять колонками и участниками, комментировать, назначать исполнителей и дедлайны.

У Ёжки нет публичного API, поэтому сервер работает через внутренний REST API веб-приложения (`yozhka.lukit.ru/backend`), reverse-engineering от ноября 2026. API может измениться без предупреждения. Для личного использования; проект не связан с Лукит/Ростелеком.

## Установка на Windows

Работай в PowerShell (Пуск → набери «PowerShell»). Каждый шаг — копипаста.

**1. Поставить uv** (и Git, если его нет). Через winget:

```powershell
winget install --id astral-sh.uv -e
winget install --id Git.Git -e          # только если git ещё не установлен
```

или через Chocolatey, если она у тебя уже стоит:

```powershell
choco install uv -y
choco install git -y                    # только если git ещё не установлен
```

После установки закрой и снова открой PowerShell (чтобы обновился PATH). Проверка: `uv --version` — печатает версию.

**2. Скачать проект и поставить зависимости** (путь будет `C:\Users\ТВОЙ_ЮЗЕР\yozhka-mcp`):

```powershell
git clone https://github.com/majormnb/YozhkaMCP "$env:USERPROFILE\yozhka-mcp"
cd "$env:USERPROFILE\yozhka-mcp"
uv sync
```

**3. Положить токен.** Открой https://yozhka.lukit.ru, войди, нажми F12 → вкладка Console → вставь туда:

```js
copy(JSON.parse(localStorage.getItem('ejka.refreshToken')))
```

Токен скопировался в буфер обмена. Теперь создай файл с токеном:

```powershell
notepad .env
```

Notepad спросит «создать файл?» — да. Вставь одну строку (Ctrl+V): `YOZHKA_REFRESH_TOKEN=ВСТАВЬ_СЮДА`, сохрани (Ctrl+S), закрой.

**4. Подключить к своему AI-клиенту** — пути виндовые, с двойными обратными слешами в JSON:

```json
{
  "mcp": {
    "servers": {
      "yozhka": {
        "type": "stdio",
        "command": "C:\\Users\\ТВОЙ_ЮЗЕР\\.local\\bin\\uv.exe",
        "args": ["run", "--directory", "C:\\Users\\ТВОЙ_ЮЗЕР\\yozhka-mcp", "yozhka-mcp"]
      }
    }
  }
}
```

ZCode — этот блок в `C:\Users\ТВОЙ_ЮЗЕР\.zcode\cli\config.json`. Claude Desktop — в `%APPDATA%\Claude\claude_desktop_config.json` (вставь этот путь в адресную строку Проводника), там ключ `mcpServers` вместо `mcp.servers` (примеры ниже, в разделе «Подключение к клиентам»).

В двух местах замени на своё: `ТВОЙ_ЮЗЕР` — твоё имя в Windows (видно в PowerShell до `>`), а если `command` не сработает — проверь путь командой `(Get-Command uv).Source` и вставь то, что она напечатает.

**Готово.** Перезапусти клиент — у ассистента появятся инструменты Ёжки (проверить: «сколько у меня задач в Ёжке?»).

## Установка на macOS

Нужен [Homebrew](https://brew.sh). Каждый шаг — копипаста в Терминал.

**1. Поставить uv** (менеджер Python-окружений, один раз):

```bash
brew install uv
```

**2. Скачать проект и поставить зависимости:**

```bash
git clone https://github.com/majormnb/YozhkaMCP ~/yozhka-mcp && cd ~/yozhka-mcp && uv sync
```

**3. Положить токен.** Токен достаётся так же, как на Windows: https://yozhka.lukit.ru → F12 → Console → `copy(JSON.parse(localStorage.getItem('ejka.refreshToken')))` → он в буфере. Теперь в терминале (вместо `ВСТАВЬ_СЮДА` — твой скопированный токен, вставляется Cmd+V):

```bash
echo 'YOZHKA_REFRESH_TOKEN=ВСТАВЬ_СЮДА' > .env
```

**4. Подключить к своему AI-клиенту.**

ZCode — в `~/.zcode/cli/config.json`:

```json
{
  "mcp": {
    "servers": {
      "yozhka": {
        "type": "stdio",
        "command": "/opt/homebrew/bin/uv",
        "args": ["run", "--directory", "/Users/ТВОЙ_ЮЗЕР/yozhka-mcp", "yozhka-mcp"]
      }
    }
  }
}
```

Claude Desktop — то же самое, но файл называется `~/Library/Application Support/Claude/claude_desktop_config.json`, ключ `mcpServers` вместо `mcp.servers` (примеры ниже, в разделе «Подключение к клиентам»).

В двух местах замени на своё: `ТВОЙ_ЮЗЕР` — твоё имя на Mac (видно в Терминале до `@`), а если `command` не сработает — проверь путь командой `which uv` и вставь то, что она напечатает.

**Готово.** Перезапусти клиент и спроси у ассистента про задачи в Ёжке.

Если что-то не завелось — раздел «Проверка» ниже. Остальные способы запуска (Docker, серверный режим) — не нужны, пока не захочешь.

## Возможности

61 инструмент, сгруппированный по доменам:

- **Пространства** — список, детали, создание, переименование, участники, приглашения по email, роли, лимиты тарифа
- **Проекты** — список (активные / избранные / архив), детали, создание, переименование, архивация и восстановление, избранное, участники
- **Колонки доски** — список, создание, переименование, смена цвета, удаление
- **Задачи** — список и поиск, детали, создание, редактирование, перемещение между колонками и между проектами, копирование, приоритет, дедлайн, исполнители, наблюдатели, метки, отметка выполнения, повторяющиеся задачи (PRO), удаление, история изменений, экспорт в xlsx/csv
- **Мои задачи** — все назначенные на меня задачи во всех пространствах, задачи с дедлайнами и без («ежедневник»)
- **Чек-листы** — пункты и отметки, правка пункта (название, дата, исполнители), удаление, преобразование пункта в отдельную задачу
- **Комментарии** — список, добавление (в том числе ответы), правка, удаление
- **Вложения** — список, загрузка, скачивание, удаление файлов на задачах
- **Упоминания и ссылки** — `@[email]` превращается в «живой» тег Ёжки, `[текст](https://…)` — в кликабельную ссылку (только http/https); обычный «@имя» остаётся текстом. Весь прочий текст экранируется: HTML-разметка из сообщения ассистента не уедет коллегам как «сырой» HTML
- **Пользователи и уведомления** — профиль, поиск по email, лента уведомлений, отметка прочитанными
- **Подтверждение опасных действий** — изменение описания и удаление задач без `confirm=true` возвращают вопрос «вы уверены?» и ничего не меняют; ассистент обязан спросить пользователя и повторить вызов только после явного «да»

Режим только для чтения включается переменной `YOZHKA_READ_ONLY=true`: write-инструменты не регистрируются вообще, плюс внутренняя проверка в каждом вызове (двойная защита).

## Требования

- Windows 10/11 или macOS
- [uv](https://docs.astral.sh/uv/) (ставится в разделе «Установка» под твою ОС) — сам подтянет Python 3.11+, отдельно Python ставить не нужно
- Git (Windows: ставится той же командой winget/choco; macOS: входит в Xcode Command Line Tools)
- Учётная запись Ёжки с доступом к веб-версии

## Токен

Ёжка авторизуется через Keycloak SSO. Серверу нужен refresh-токен (живёт около 30 дней), access-токен он получает и обновляет сам.

1. Откройте https://yozhka.lukit.ru и войдите.
2. Откройте DevTools (F12), вкладка Console, выполните:
   ```js
   copy(JSON.parse(localStorage.getItem('ejka.refreshToken')))
   ```
   Токен скопируется в буфер обмена.
3. Создайте файл `.env` в корне репозитория и вставьте токен:
   ```
   YOZHKA_REFRESH_TOKEN=eyJhbGciOiJIUzUxMiIs...
   ```
4. Примерно раз в 30 дней сессия истечёт — повторите шаги.

Файл `.env` добавлен в `.gitignore` и не попадает в репозиторий и Docker-образ. Ограничьте права: `chmod 600 .env` — refresh-токен даёт полный доступ к аккаунту.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `YOZHKA_REFRESH_TOKEN` | — | refresh-токен, основной способ авторизации |
| `YOZHKA_ACCESS_TOKEN` | — | готовый access-токен (живёт ~1 час), альтернатива для отладки |
| `YOZHKA_BASE_URL` | `https://yozhka.lukit.ru/backend` | адрес API |
| `YOZHKA_READ_ONLY` | `false` | `true` — без write-инструментов |
| `YOZHKA_TIMEOUT` | `30` | таймаут запроса, секунды |
| `YOZHKA_MAX_RETRIES` | `3` | число повторов при 429/5xx |
| `YOZHKA_TRANSPORT` | `stdio` | `stdio` или `http` (streamable-http, для Docker-сервиса) |
| `YOZHKA_HOST` / `YOZHKA_PORT` | `127.0.0.1` / `8000` | адрес и порт в http-режиме |
| `YOZHKA_HTTP_TOKEN` | — | токен http-режима: клиенты передают `Authorization: Bearer <token>` или заголовок `X-MCP-Token` |
| `YOZHKA_DEBUG` | `false` | отладочные логи |

## Подключение к клиентам

Во всех примерах замените путь на свой.

### ZCode

`~/.zcode/cli/config.json`:

```json
{
  "mcp": {
    "servers": {
      "yozhka": {
        "type": "stdio",
        "command": "/opt/homebrew/bin/uv",
        "args": ["run", "--directory", "/Users/USER/yozhka-mcp", "yozhka-mcp"]
      }
    }
  }
}
```

Путь к `uv` лучше указать абсолютный: у GUI-приложений часто нет `/opt/homebrew/bin` в `PATH`. Токен в конфиг не нужен — сервер читает `.env` из каталога проекта.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yozhka": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/USER/yozhka-mcp", "yozhka-mcp"]
    }
  }
}
```

### Cursor

`.cursor/mcp.json` в проекте или `~/.cursor/mcp.json` глобально:

```json
{
  "mcpServers": {
    "yozhka": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/USER/yozhka-mcp", "yozhka-mcp"]
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
      "command": ["uv", "run", "--directory", "/Users/USER/yozhka-mcp", "yozhka-mcp"]
    }
  }
}
```

## Способы запуска

### Локально через uv (stdio)

Основной режим: MCP-клиент сам запускает процесс на каждую сессию и общается с ним по stdin/stdout. Демона нет, порт не занимается. Конфигурация — в разделе выше.

### Docker (stdio)

Если не хочется держать Python и uv на хосте:

```bash
docker build -t yozhka-mcp .
```

Конфигурация клиента:

```json
{
  "mcpServers": {
    "yozhka": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--env-file", "/Users/USER/yozhka-mcp/.env", "yozhka-mcp"]
    }
  }
}
```

Флаг `-i` обязателен, `-t` нельзя — TTY ломает JSON-RPC. Токен передаётся в рантайме, в образ он не попадает.

### Docker как сервис (HTTP)

Долгоживущий контейнер, клиенты подключаются по URL `http://localhost:8000/mcp`. Удобно, когда одним сервером пользуются несколько клиентов или машин:

```bash
docker compose up -d --build
```

Конфигурация клиентов для URL-подключения:

```json
{"mcpServers": {"yozhka": {"url": "http://localhost:8000/mcp"}}}
```

```json
{"mcp": {"yozhka": {"type": "remote", "url": "http://localhost:8000/mcp"}}}
```

(первый вариант — ZCode/Cursor, второй — OpenCode)

Важно: HTTP-эндпоинт по умолчанию не требует авторизации — любой процесс, дотянувшийся до порта, получит доступ к вашей Ёжке (сюда входят и атаки DNS-rebinding из браузера). Поэтому сервер без `YOZHKA_HTTP_TOKEN` принимает запросы только с localhost, а compose публикует порт на `127.0.0.1`. Если пробрасываете порт дальше — задайте `YOZHKA_HTTP_TOKEN` и передавайте его в заголовке `Authorization: Bearer …` или `X-MCP-Token`. Для доступа с других машин — SSH-туннель или обратный прокси с авторизацией; крайний случай — `YOZHKA_READ_ONLY=true`.

### Alpine-образ

Зависимости проекта — чистый Python плюс musl-совместимые wheels, поэтому доступен и alpine (222 МБ вместо 352 у slim):

```bash
docker build --build-arg BASE=ghcr.io/astral-sh/uv:python3.12-alpine \
  --build-arg RUNTIME=python:3.12-alpine -t yozhka-mcp:alpine .
```

Если добавите зависимость с C-расширением без musllinux-wheel — вернитесь на образ по умолчанию.

## Проверка

```bash
# тесты
uv run pytest

# интерактивная проверка через MCP Inspector
uv run mcp dev src/yozhka_mcp/server.py
```

## Структура проекта

```
src/yozhka_mcp/
  server.py             # FastMCP, регистрация инструментов, READ_ONLY
  config.py             # конфигурация из переменных окружения
  api/
    client.py           # httpx, Bearer, авто-refresh, повторы
    endpoints.py        # все пути API в одном месте
    exceptions.py       # AuthError, NotFoundError, PermissionDeniedError и др.
  tools/                # инструменты по доменам: workspaces, projects, columns,
                        # tasks, checklists, comments, misc, auth
tests/                  # моки respx + клиент fastmcp in-memory
research/               # результаты reverse-engineering API
```

## Подтверждение опасных действий

Правила гейта (первый вызов возвращает вопрос и **ничего не делает**, ассистент обязан спросить пользователя и повторить вызов с `confirm=true` только после явного «да»):

- **Чужая задача** (автор — другой пользователь): гейт на изменение `title` и/или `description` через `update_task`
- **Любая задача, включая свою**: гейт на удаление через `delete_task`
- Не гейтится: изменение `title`/`description` **своей** задачи, перемещения, комментарии, чек-листы

Пример ответа:

```json
{
  "confirmation_required": true,
  "task": "UBERPEPOLS-36",
  "action": "delete_task",
  "task_title": "Потестить cloudflare warp",
  "message": "Вы уверены, что хотите УДАЛИТЬ задачу …? Действие необратимо. …"
}
```

Политика продублирована в инструкции сервера (`instructions`), поэтому корректные MCP-клиенты знают о ней до первого вызова.

## Известные особенности API

Всё специфичное для API собрано в `api/endpoints.py`, чтобы при изменениях править в одном месте. Основные нюансы, узнанные живыми запросами: `PUT /task` и `PUT /comment` требуют полного объекта; id колонок уникальны для каждого проекта; текстовые поля — HTML (сервер экранирует всё сам, «живыми» остаются только упоминания, собранные сервером MCP); дедлайны задаются по московскому времени (+03:00); даты без значения кодируются сентинелом `2999-12-31T00:00:00Z`.

## Отказ от ответственности

Проект не связан с Лукит и Ростелеком, использует приватное API. Соблюдайте пользовательское соглашение сервиса и не злоупотребляйте количеством запросов (в клиенте есть повторы с экспоненциальной паузой).

## Лицензия

MIT
