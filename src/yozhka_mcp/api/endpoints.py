"""Каталог реверснутых эндпоинтов API Ёжки.

Единственное место, где живут пути API. Если сервис изменит API —
правим только этот файл (см. research/endpoints.md для контекста).

Base URL: https://yozhka.lukit.ru/backend  (см. config.DEFAULT_BASE_URL)
"""

# --- Auth (Keycloak SSO) ---
AUTH_ENTRY = "/auth"            # точка входа SSO (public, ?redirectUrl=)
AUTH_LOGIN = "/auth/login"
AUTH_REFRESH = "/auth/refresh"
AUTH_ME = "/auth/me"
AUTH_TOKEN = "/auth/token"
AUTH_LOGOUT = "/auth/logout"

# --- Projects ---
PROJECT_LIST = "/project/list"
PROJECT_LIST_MY = "/project/list/my"
PROJECT_TILES_MY = "/project/tiles/my"
PROJECT_TITLES_MY = "/project/titles/my"
PROJECT_SEARCH = "/project/search/{query}"
PROJECT_BY_CODE = "/project/code/{code}"
PROJECT_GENERATE_MCODE = "/project/generateMCode"
PROJECT_DETAIL = "/project/{project_id}"
PROJECT_UPDATE_STATE = "/project/updateProjectState"
PROJECT_FAVORITES = "/project/favorites/{project_id}"
PROJECT_ADD_USERS = "/project/{project_id}/addUsers"
PROJECT_DELETE_USER = "/project/{project_id}/deleteUser"
PROJECT_USERS = "/project/{project_id}/users"
PROJECT_ACTIVE_USERS = "/project/{project_id}/activeUsers"
PROJECT_ROLE = "/project/role"

# --- Users / profiles ---
USER_PROFILE = "/userProfile"
USER_PROFILE_FIND = "/userProfile/find/{query}"
USER_PROFILE_FIND_BY_IDS = "/userProfile/findByIds"
USER_PROFILE_FIND_BY_EMAILS = "/userProfile/findByEmails"
USER_PROFILE_SAVE = "/userProfile/save"
USER_PROFILE_SAVE_EXTERNAL = "/userProfile/saveExternal"

# --- Attachments (attacher-сервис) ---
ATTACHMENT_LIST = "/getAttachment/list"

# --- Прочее ---
TASK_ASSIGNEE_CNT = "/taskAssignee/cnt/{user_id}"
FEEDBACK = "/feedback"

# --- Tasks / columns / comments ---
# ЗАПОЛНЯЕТСЯ ПО РЕЗУЛЬТАТАМ РЕВЕРСА ЧЕРЕЗ БРАУЗЕР (research/endpoints.md)
