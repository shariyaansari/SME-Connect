from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class StepExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepExecutionResponse(BaseModel):
    id: int
    execution_id: int
    step_id: str
    step_index: int
    status: str
    failure_category: str | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class ExecutionSummary(BaseModel):
    id: int
    workflow_id: int
    workflow_version_id: int
    workflow_name: str | None = None
    organization_id: int
    status: str
    attempt_number: int = 1
    retry_count: int = 0
    retry_of_execution_id: int | None = None
    next_retry_at: datetime | None = None
    failure_category: str | None = None
    last_error_at: datetime | None = None
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime


class ExecutionDetail(BaseModel):
    id: int
    workflow_id: int
    workflow_version_id: int
    workflow_name: str | None = None
    organization_id: int
    status: str
    attempt_number: int = 1
    retry_count: int = 0
    retry_of_execution_id: int | None = None
    next_retry_at: datetime | None = None
    failure_category: str | None = None
    last_error_at: datetime | None = None
    trigger_data: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    steps: list[StepExecutionResponse] = Field(default_factory=list)
    failure_title: str | None = None
    failure_explanation: str | None = None
    actionable_guidance: str | None = None
    can_manual_retry: bool = False


class ExecutionTriggerRequest(BaseModel):
    trigger_data: dict[str, Any] = Field(default_factory=dict)
