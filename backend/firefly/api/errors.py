"""統一錯誤格式 / Uniform error format(文件 06):{ error: { code, message_zh, message_en } }。"""
from __future__ import annotations

from fastapi import HTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, zh: str, en: str, headers: dict | None = None):
        super().__init__(status_code=status, detail={"code": code, "message_zh": zh, "message_en": en}, headers=headers)


def not_found(code: str = "not_found") -> ApiError:
    return ApiError(404, code, "找不到資源", "Resource not found")


def unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "需要有效的代號", "A valid token is required")


def forbidden(zh: str, en: str) -> ApiError:
    return ApiError(403, "forbidden", zh, en)


def too_many(retry_after: int) -> ApiError:
    return ApiError(429, "rate_limited", "請求過於頻繁", "Too many requests", headers={"Retry-After": str(retry_after)})
