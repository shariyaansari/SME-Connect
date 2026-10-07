from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ConnectorCatalogItemResponse(BaseModel):
    slug: str
    name: str
    category: str
    description: str
    icon: str
    auth_type: str
    config_fields: list[dict[str, Any]]
    credential_fields: list[dict[str, Any]]
    supported_triggers: list[dict[str, Any]]
    supported_actions: list[dict[str, Any]]


class ConnectionCreateRequest(BaseModel):
    connector_slug: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=150)
    auth_type: str = "api_key"
    config: dict[str, Any] = Field(default_factory=dict)
    credentials: dict[str, Any] = Field(default_factory=dict)


class ConnectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    config: dict[str, Any] | None = None
    credentials: dict[str, Any] | None = None


class ConnectionResponse(BaseModel):
    id: int
    organization_id: int
    connector_slug: str
    name: str
    auth_type: str
    config: dict[str, Any]
    masked_credentials: dict[str, str]
    status: str
    last_tested_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ConnectionTestResponse(BaseModel):
    success: bool
    status: str
    message: str
    tested_at: datetime
