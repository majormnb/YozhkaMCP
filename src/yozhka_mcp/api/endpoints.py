"""Каталог реверснутых эндпоинтов API Ёжки.

Единственное место, где живут пути API. Источник: research/endpoints.md
(реверс через браузер 2026-11-22). При drift API правим только этот файл.

Base URL: https://yozhka.lukit.ru/backend  (config.DEFAULT_BASE_URL)
"""

# --- Auth (Keycloak, realm bun) ---
AUTH_REFRESH = "/auth/refresh"   # POST {refreshToken} -> {accessToken, refreshToken}
AUTH_ME = "/auth/me"

# --- Workspaces ---
WORKSPACE_GENERATE_MCODE = "/workspace/generateMCode"      # POST "Название" -> "CODE"
WORKSPACE = "/workspace"                                   # POST create / PUT update
WORKSPACE_MY = "/workspace/my"                             # GET ?page=1&size=
WORKSPACE_BY_CODE = "/workspace/{code}"                    # GET / DELETE(?)
WORKSPACE_USERS = "/workspace/{workspace_id}/users"        # GET
WORKSPACE_ADD_USERS = "/workspaces/{workspace_id}/addUsers"  # POST {mails, roleId} — ВНИМАНИЕ: мн.ч.!
WORKSPACE_ROLE_LIST = "/workspace/role/list"               # GET
WORKSPACE_LIMITS = "/workspaceSubscription/{workspace_id}/limits"  # GET
SUBSCRIPTION_TYPES = "/workspaceSubscription/subscriptionType/list"  # GET

# --- Workspace tags ---
WORKSPACE_TAG = "/workspaceTag/{workspace_id}"             # GET ?page&size&search
WORKSPACE_TAG_CREATE = "/workspaceTag"                     # POST {tagName, workspaceId, backgroundColor}

# --- Projects ---
PROJECT_GENERATE_MCODE = "/project/generateMCode"          # POST ?projectName=&workspaceId=
PROJECT = "/project"                                       # POST create / PUT update
PROJECT_TILES_MY = "/project/tiles/my"                     # GET ?workspaceId=&stateFilter=
PROJECT_TITLES_MY = "/project/titles/my"                   # GET (компактный)
PROJECT_BY_CODE = "/project/code/{code}/{workspace_id}"    # GET
PROJECT_BY_ID = "/project/{project_id}/{workspace_id}"     # GET
PROJECT_UPDATE_STATE = "/project/updateProjectState"       # POST ?workspaceId&projectId&targetProjectStateId (1|2)
PROJECT_FAVORITES = "/project/favorites/{project_id}"      # POST toggle
PROJECT_USERS = "/project/{project_id}/users"              # GET
PROJECT_ACTIVE_USERS = "/project/{project_id}/activeUsers" # GET

# --- Канбан-колонки (статусы) ---
WORKFLOW_STATUSES = "/workflowStatusesAvail"               # GET ?projectId= / POST / PUT / DELETE

# --- Tasks ---
TASK = "/task"                                             # POST ?onTop=true / PUT (полный объект)
TASK_LIST = "/task/{project_id}/list"                      # GET ?page=0&size=&searchText=
TASK_SEARCH = "/task/searchByProjectId/{project_id}"       # GET ?searchText=
TASK_BY_CODE = "/task/code/{task_code}"                    # GET
TASK_BY_ID = "/task/{task_id}"                             # DELETE
TASK_PRIORITY = "/taskPriority"                            # GET
TASK_HISTORY = "/task/{task_id}/history"                   # GET ?page=0&size=

# --- Чек-листы ---
CHECKLIST_LIST = "/checklist/{task_id}/list"               # GET ?page=0&size=&searchText=
CHECKLIST = "/checklist"                                   # POST {taskId, itemTitle, ...}
CHECKLIST_MARK = "/checklist/mark/{item_id}"               # POST {itemId, taskId, returnValue}

# --- Комментарии ---
COMMENT_LIST = "/comment/{task_id}/list"                   # GET ?page=0&size=&search=&filter={}
COMMENT = "/comment"                                       # POST {contentComment, taskId, ...}

# --- Пользователи ---
USER_PROFILE = "/userProfile"                              # GET (мой профиль)
USER_PROFILE_FIND = "/userProfile/find/{email}"            # GET

# --- Уведомления ---
NOTIFICATIONS = "/notifications"                           # GET ?page=1&size=&search=

# --- Значения справочников ---
PROJECT_STATE_ACTIVE = 1
PROJECT_STATE_ARCHIVE = 2
TASK_TYPE_DEFAULT = 2
HIERARCHY_LEVEL_DEFAULT = 2
FOREVER = "2999-12-31T00:00:00Z"
