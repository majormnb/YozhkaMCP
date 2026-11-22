"""Исключения API-слоя yozhka-mcp."""


class YozhkaError(Exception):
    """Базовая ошибка при работе с API Ёжки."""

    def __init__(self, message: str, *, status_code: int | None = None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class AuthError(YozhkaError):
    """Токен отсутствует, истёк или не проходит refresh."""


class NotFoundError(YozhkaError):
    """Сущность не найдена (404)."""


class PermissionDeniedError(YozhkaError):
    """Недостаточно прав в проекте (403)."""


class ValidationError(YozhkaError):
    """Сервер отклонил тело запроса (400/422)."""


class RateLimitError(YozhkaError):
    """429 — превышен лимит запросов (после всех ретраев)."""


class ApiError(YozhkaError):
    """Прочие ошибки API (5xx и нестандартные ответы)."""
