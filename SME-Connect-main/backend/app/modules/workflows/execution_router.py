from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.database.models import Membership, User
from app.core.security import get_current_user
from app.modules.audit.service import create_audit_log
from app.modules.workflows.execution_service import (
    get_execution,
    list_executions,
    retry_workflow_execution,
    to_execution_detail,
    to_execution_summary,
)
from app.modules.workflows.schemas import ExecutionDetail, ExecutionSummary

router = APIRouter(prefix="/executions", tags=["Executions"])

VALID_STATUSES = {"pending", "running", "success", "failed"}


@router.get(
    "",
    response_model=list[ExecutionSummary],
    status_code=http_status.HTTP_200_OK,
)
def list_executions_endpoint(
    workflow_id: int | None = Query(None, description="Filter by workflow ID"),
    organization_id: int | None = Query(None, description="Filter by organization ID"),
    status: str | None = Query(None, description="Filter by status: pending, running, success, failed"),
    start_date: datetime | None = Query(None, description="Filter executions started on or after timestamp"),
    end_date: datetime | None = Query(None, description="Filter executions started on or before timestamp"),
    limit: int = Query(50, ge=1, le=100, description="Number of executions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists workflow executions for the authenticated user's organization.
    Supports filtering by workflow_id, status, date range, and pagination.
    """
    if status is not None and status.lower() not in VALID_STATUSES:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status filter '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
        )

    try:
        executions = list_executions(
            db=db,
            workflow_id=workflow_id,
            status_filter=status.lower() if status else None,
            start_date=start_date,
            end_date=end_date,
            user_id=current_user.id,
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )
        return [to_execution_summary(e) for e in executions]
    except PermissionError as err:
        raise HTTPException(status_code=403, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get(
    "/{execution_id}",
    response_model=ExecutionDetail,
    status_code=http_status.HTTP_200_OK,
)
def get_execution_detail_endpoint(
    execution_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves full execution details, including chronological step execution results,
    sanitized payloads, condition outcomes, and error messages.
    Enforces multi-tenant organization boundary security.
    """
    try:
        execution = get_execution(
            db=db,
            execution_id=execution_id,
            user_id=current_user.id,
            organization_id=organization_id,
        )
        return to_execution_detail(execution)
    except PermissionError as err:
        raise HTTPException(status_code=403, detail=str(err))
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=404, detail="Execution record not found")
        raise HTTPException(status_code=400, detail=str(err))


@router.post(
    "/{execution_id}/retry",
    response_model=ExecutionDetail,
    status_code=http_status.HTTP_200_OK,
)
def retry_execution_endpoint(
    execution_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retries a failed workflow execution.
    Preserves exact historical workflow version, original trigger context,
    enforces tenant boundaries, role-based authorization (Admin/Editor only),
    and records an audit log event.
    """
    # 1. Resolve execution and tenant membership
    try:
        execution = get_execution(
            db=db,
            execution_id=execution_id,
            user_id=current_user.id,
            organization_id=organization_id,
        )
    except Exception:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Execution record not found")

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == execution.organization_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Execution record not found")

    # 2. RBAC check: Viewers cannot trigger retries
    if str(membership.role).lower() not in {"admin", "editor"}:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail="Viewers are not permitted to retry workflow executions",
        )

    # 3. Validation: status must be failed
    if execution.status != "failed":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry execution with status '{execution.status}'. Only failed executions can be retried.",
        )

    # 4. Validation: workflow must not be paused
    if execution.workflow and execution.workflow.status == "paused":
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Cannot retry execution for a paused workflow. Resume the workflow first.",
        )

    # 5. Execute safe retry
    try:
        retried_exec = retry_workflow_execution(
            db=db,
            execution_id=execution.id,
            user_id=current_user.id,
            organization_id=execution.organization_id,
        )

        # 6. Record audit log
        create_audit_log(
            db=db,
            organization_id=execution.organization_id,
            user_id=current_user.id,
            action="WORKFLOW_EXECUTION_RETRIED",
            resource_type="workflow_execution",
            resource_id=retried_exec.id,
            details=f"Retried execution {execution.id} (new execution {retried_exec.id}, attempt {retried_exec.attempt_number})",
        )
        db.commit()

        return to_execution_detail(retried_exec)
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))

