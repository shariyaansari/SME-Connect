from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import Membership, User, Workflow, WorkflowVersion
from app.modules.connectors.registry import get_adapter
from app.modules.executions.runner import run_trigger_poll_cycle
from app.modules.executions.scheduler import run_scheduled_workflow_cycle
from app.modules.executions.schemas import (
    ExecutionDetail,
    ExecutionSummary,
    ExecutionTriggerRequest,
)
from app.modules.executions.service import (
    execute_workflow,
    get_execution,
    list_executions,
    retry_execution,
    to_detail_response,
    to_summary_response,
)

router = APIRouter(
    prefix="/executions",
    tags=["Executions"],
)


def _get_membership(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> Membership:
    query = select(Membership).where(Membership.user_id == user_id)
    if organization_id is not None:
        query = query.where(Membership.organization_id == organization_id)

    membership = db.scalar(query.order_by(Membership.id))
    if not membership:
        raise ValueError("User does not belong to the specified organization")
    return membership


@router.get(
    "",
    response_model=list[ExecutionSummary],
)
def list_executions_endpoint(
    workflow_id: int | None = Query(None, description="Filter by workflow ID"),
    status: str | None = Query(None, description="Filter by execution status (success, failed, running, pending)"),
    from_date: datetime | None = Query(None, description="Filter executions starting from this timestamp"),
    to_date: datetime | None = Query(None, description="Filter executions completed by this timestamp"),
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns filtered execution history for the organization.
    Never exposes secrets, tokens, or credential payloads.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        execs = list_executions(
            db=db,
            organization_id=membership.organization_id,
            workflow_id=workflow_id,
            status=status,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
        return [to_summary_response(e) for e in execs]
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/{execution_id}",
    response_model=ExecutionDetail,
)
def get_execution_endpoint(
    execution_id: int,
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns comprehensive execution details and step breakdown.
    Displays sanitized inputs, outputs, timestamps, and error diagnostics.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        execution = get_execution(
            db=db,
            execution_id=execution_id,
            organization_id=membership.organization_id,
        )
        return to_detail_response(execution)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "/run/{workflow_id}",
    response_model=ExecutionDetail,
)
def trigger_workflow_manual_run(
    workflow_id: int,
    body: ExecutionTriggerRequest | None = None,
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually triggers execution of a published workflow with custom or generated trigger data.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        if membership.role not in {"Admin", "Editor"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admins and Editors can manually trigger workflows",
            )

        trigger_data = body.trigger_data if body and body.trigger_data else None

        if not trigger_data:
            # Fall back to sample trigger data derived from the workflow trigger definition
            wf = db.scalar(select(Workflow).where(Workflow.id == workflow_id))
            if not wf:
                raise ValueError("Workflow not found")
            published_version = db.scalar(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == wf.id, WorkflowVersion.published_at.is_not(None))
                .order_by(WorkflowVersion.version_number.desc())
            )
            if not published_version:
                raise ValueError("Workflow has no published version to run")

            trigger_def = published_version.definition.get("trigger", {})
            conn_slug = trigger_def.get("connector", "")
            adapter = get_adapter(conn_slug)
            if adapter:
                try:
                    records, _ = adapter.read_trigger_data(trigger_def.get("event", ""), trigger_def.get("config", {}), {})
                    if records:
                        trigger_data = records[0]
                except Exception:
                    pass

            if not trigger_data:
                trigger_data = {"test_run": True, "values": {"Name": "Test Customer", "Email": "test@smeconnect.local"}}

        execution = execute_workflow(
            db=db,
            workflow_id=workflow_id,
            trigger_data=trigger_data,
            organization_id=membership.organization_id,
        )
        return to_detail_response(execution)

    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/poll-cycle",
    response_model=dict[str, Any],
)
def trigger_poll_cycle_endpoint(
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers an on-demand polling cycle for all published workflows in the organization.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        if membership.role not in {"Admin", "Editor"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admins and Editors can trigger poll cycles",
            )

        return run_trigger_poll_cycle(
            db=db,
            organization_id=membership.organization_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "/{execution_id}/retry",
    response_model=ExecutionDetail,
)
def manual_retry_execution_endpoint(
    execution_id: int,
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Manually retries a failed workflow execution (Module 6.6).
    Enforces Admin/Editor RBAC, failed-only status check, active workflow status check,
    version preservation, and tenant isolation.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        if membership.role not in {"Admin", "Editor"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admins and Editors can manually retry executions",
            )

        new_execution = retry_execution(
            db=db,
            execution_id=execution_id,
            organization_id=membership.organization_id,
        )
        return to_detail_response(new_execution)

    except ValueError as err:
        err_msg = str(err)
        if "not found" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.post(
    "/schedule-cycle",
    response_model=list[ExecutionSummary],
)
def trigger_schedule_cycle_endpoint(
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Runs an on-demand scheduler cycle for due scheduled workflows (Module 6.5).
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        if membership.role not in {"Admin", "Editor"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Admins and Editors can trigger schedule cycles",
            )

        execs = run_scheduled_workflow_cycle(
            db=db,
            organization_id=membership.organization_id,
        )
        return [to_summary_response(e) for e in execs]
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
