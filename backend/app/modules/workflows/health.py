from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Workflow, WorkflowExecution
from app.modules.executions.resolver import sanitize_error_message
from app.modules.executions.retry_policy import explain_failure_for_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowHealthStatus(str, Enum):
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    PAUSED = "paused"
    NEVER_RUN = "never_run"
    RETRYING = "retrying"


class WorkflowHealthResponse(BaseModel):
    workflow_id: int
    health_status: WorkflowHealthStatus
    health_message: str
    last_execution_status: str | None = None
    last_execution_at: datetime | None = None
    last_successful_execution_at: datetime | None = None
    last_failed_execution_at: datetime | None = None
    last_error_message: str | None = None
    failure_category: str | None = None
    consecutive_failures: int = 0
    total_recent_executions: int = 0
    recent_success_rate: float | None = None
    is_retrying: bool = False
    next_retry_at: datetime | None = None


def calculate_workflow_health(
    db: Session,
    workflow_id: int,
    organization_id: int | None = None,
) -> WorkflowHealthResponse:
    """
    Derives lightweight, operational health metrics for an SME workflow (Module 6.7).
    Derives state from execution history without maintaining redundant counters.
    Guarantees strict tenant isolation.
    """
    query = select(Workflow).where(Workflow.id == workflow_id)
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflow = db.scalar(query)
    if not workflow:
        raise ValueError("Workflow not found")
    db.refresh(workflow)

    # 1. Paused state takes precedence
    if workflow.status == "paused":
        return WorkflowHealthResponse(
            workflow_id=workflow.id,
            health_status=WorkflowHealthStatus.PAUSED,
            health_message="This workflow is currently paused and will not execute until resumed.",
            consecutive_failures=0,
            total_recent_executions=0,
        )

    # 2. Query recent executions (up to 20 for calculating metrics)
    exec_query = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_id == workflow.id,
            WorkflowExecution.organization_id == workflow.organization_id,
        )
        .order_by(WorkflowExecution.created_at.desc())
        .limit(20)
    )
    recent_execs = list(db.scalars(exec_query).all())

    # 3. Never run state
    if not recent_execs:
        return WorkflowHealthResponse(
            workflow_id=workflow.id,
            health_status=WorkflowHealthStatus.NEVER_RUN,
            health_message="This workflow is published and ready to run when triggered.",
            consecutive_failures=0,
            total_recent_executions=0,
        )

    latest_exec = recent_execs[0]
    total_count = len(recent_execs)
    successes = [e for e in recent_execs if e.status == "success"]
    failures = [e for e in recent_execs if e.status == "failed"]

    # Calculate consecutive failures
    consecutive_failures = 0
    for e in recent_execs:
        if e.status == "failed":
            consecutive_failures += 1
        elif e.status == "success":
            break

    # Calculate success rate
    success_rate = round((len(successes) / total_count) * 100, 1) if total_count > 0 else None

    # Timestamps
    last_success_at = max((e.completed_at for e in successes if e.completed_at), default=None)
    last_failure_at = max((e.completed_at for e in failures if e.completed_at), default=None)

    now = _utc_now()
    next_retry = latest_exec.next_retry_at
    if next_retry is not None and next_retry.tzinfo is None:
        next_retry = next_retry.replace(tzinfo=timezone.utc)
    is_retrying = bool(
        latest_exec.status == "failed"
        and next_retry is not None
        and next_retry > now
    )

    # Determine health status & friendly message
    if is_retrying:
        health_status = WorkflowHealthStatus.RETRYING
        health_msg = f"A recent run failed and is scheduled to retry at {latest_exec.next_retry_at.strftime('%H:%M UTC')}."
    elif latest_exec.status == "failed":
        health_status = WorkflowHealthStatus.NEEDS_ATTENTION
        exp = explain_failure_for_user(latest_exec.failure_category, latest_exec.error_message)
        health_msg = f"{exp['title']}: {exp['explanation']}"
    elif latest_exec.status == "success":
        health_status = WorkflowHealthStatus.HEALTHY
        health_msg = "Workflow is operating normally. Recent runs completed successfully."
    else:
        health_status = WorkflowHealthStatus.HEALTHY
        health_msg = f"Workflow execution is currently {latest_exec.status}."

    return WorkflowHealthResponse(
        workflow_id=workflow.id,
        health_status=health_status,
        health_message=health_msg,
        last_execution_status=latest_exec.status,
        last_execution_at=latest_exec.started_at or latest_exec.created_at,
        last_successful_execution_at=last_success_at,
        last_failed_execution_at=last_failure_at,
        last_error_message=sanitize_error_message(latest_exec.error_message),
        failure_category=latest_exec.failure_category,
        consecutive_failures=consecutive_failures,
        total_recent_executions=total_count,
        recent_success_rate=success_rate,
        is_retrying=is_retrying,
        next_retry_at=latest_exec.next_retry_at,
    )
