from datetime import datetime
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: int
    organization_id: int
    workflow_id: int | None = None
    workflow_name: str | None = None
    execution_id: int | None = None
    title: str
    message: str
    severity: str
    notification_type: str
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread_count: int
