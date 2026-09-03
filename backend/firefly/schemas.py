"""API 請求/回應 schema / API request-response schemas(文件 06)。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .models import FlagKind


class ErrorBody(BaseModel):
    code: str
    message_zh: str
    message_en: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class DeviceIssued(BaseModel):
    device_token: str


class LookupRequest(BaseModel):
    url: str = Field(min_length=4, max_length=2048)


class VoteRequest(BaseModel):
    helpful: bool


class VoteResponse(BaseModel):
    accepted: bool = True
    counted: bool  # False = 尚未達資格,票已保存但權重 0 / saved with weight 0 until eligible


class FlagRequest(BaseModel):
    kind: FlagKind
    post_url: str | None = Field(default=None, max_length=2048)
    note: str | None = Field(default=None, max_length=1000)


class ProfileUpdate(BaseModel):
    named_profile: str = Field(min_length=2, max_length=64, pattern=r"^[\w一-鿿぀-ヿ\- ]+$")


class ContributorMe(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    origin: str
    named_profile: str | None
    lookup_count: int
    eligible: bool
