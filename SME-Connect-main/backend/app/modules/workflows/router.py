from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User, Workflow
from app.modules.workflows.execution_service import execute_workflow, to_execution_detail
from app.modules.workflows.trigger_service import poll_workflow_trigger, run_trigger_poll_cycle
from app.modules.workflows.schemas import (
    ConnectorCapabilityResponse,
    ExecutionDetail,
    ExecutionSummary,
    WorkflowCreateRequest,
    WorkflowDetailResponse,
    WorkflowExecutionRequest,
    WorkflowHealthResponse,
    WorkflowSummaryResponse,
    WorkflowUpdateRequest,
)
from app.modules.workflows.service import (
    create_workflow,
    delete_workflow,
    get_connector_capability,
    get_workflow,
    get_workflow_capabilities,
    list_workflows,
    pause_workflow,
    publish_workflow,
    update_workflow,
)
from app.modules.workflows.validation import WorkflowValidationError

router = APIRouter(
    prefix="/workflows",
    tags=["Workflows"],
)


@router.post(
    "",
    response_model=WorkflowDetailResponse,
    status_code=http_status.HTTP_201_CREATED,
)
def create_workflow_endpoint(
    data: WorkflowCreateRequest,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Creates a new workflow in draft status with version 1.
    Organization boundary is resolved automatically from the authenticated user.
    """
    try:
        return create_workflow(
            db=db,
            user_id=current_user.id,
            data=data,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except WorkflowValidationError as err:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in err.errors],
        )
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get(
    "",
    response_model=list[WorkflowSummaryResponse],
)
def list_workflows_endpoint(
    status: str | None = Query(None, description="Optional filter by status (draft, published, paused)"),
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists workflows for the user's organization.
    """
    try:
        return list_workflows(
            db=db,
            user_id=current_user.id,
            organization_id=organization_id,
            status_filter=status,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/capabilities",
    response_model=list[ConnectorCapabilityResponse],
)
def list_capabilities_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns available connector capabilities with organization connection availability.
    """
    try:
        return get_workflow_capabilities(
            db=db,
            user_id=current_user.id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/capabilities/{connector_slug}",
    response_model=ConnectorCapabilityResponse,
)
def get_capability_endpoint(
    connector_slug: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns capabilities and connection availability for a specific connector.
    """
    try:
        return get_connector_capability(
            db=db,
            user_id=current_user.id,
            connector_slug=connector_slug,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "/schedule/run-cycle",
    status_code=http_status.HTTP_200_OK,
)
def run_schedule_cycle_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Evaluates and triggers all published workflows configured with a schedule trigger
    whose scheduled recurrence slot is due. Idempotent and connector-agnostic.
    """
    from app.modules.workflows.service import _get_membership
    from app.modules.workflows.scheduler_service import run_scheduled_workflow_cycle
    try:
        membership = _get_membership(db, current_user.id)
        executions = run_scheduled_workflow_cycle(
            db=db,
            organization_id=membership.organization_id,
        )
        return {
            "status": "success",
            "triggered_count": len(executions),
            "execution_ids": [e.id for e in executions],
        }
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDetailResponse,
)
def get_workflow_endpoint(
    workflow_id: int,
    version: int | None = Query(None, description="Optional specific version number"),
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Retrieves workflow details and definition.
    Defaults to the latest version, or returns a specific version if ?version=N is requested.
    """
    try:
        return get_workflow(
            db=db,
            user_id=current_user.id,
            workflow_id=workflow_id,
            organization_id=organization_id,
            version_number=version,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))


@router.put(
    "/{workflow_id}",
    response_model=WorkflowDetailResponse,
)
def update_workflow_endpoint(
    workflow_id: int,
    data: WorkflowUpdateRequest,
    version: int | None = Query(None, description="Optional target version number to edit"),
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Updates workflow metadata (name, description) or definition.
    If the workflow is currently published, editing spawns a new draft version.
    Published workflow versions are immutable and cannot be modified directly.
    """
    try:
        return update_workflow(
            db=db,
            user_id=current_user.id,
            workflow_id=workflow_id,
            data=data,
            target_version_number=version,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except WorkflowValidationError as err:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in err.errors],
        )
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete(
    "/{workflow_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
def delete_workflow_endpoint(
    workflow_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes the workflow and cascades deletion to all versions.
    """
    try:
        delete_workflow(
            db=db,
            user_id=current_user.id,
            workflow_id=workflow_id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))



@router.post(
    "/{workflow_id}/publish",
    response_model=WorkflowDetailResponse,
)
def publish_workflow_endpoint(
    workflow_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Validates and publishes a workflow.
    Dual semantics:
      - If in Draft status: publishes the latest draft version, stamping published_at.
      - If in Paused status: resumes execution eligibility of the existing published version.
    Ensures all referenced connectors have active connections in the organization.
    """
    try:
        return publish_workflow(
            db=db,
            user_id=current_user.id,
            workflow_id=workflow_id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except WorkflowValidationError as err:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in err.errors],
        )
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/{workflow_id}/pause",
    response_model=WorkflowDetailResponse,
)
def pause_workflow_endpoint(
    workflow_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Pauses an active workflow without modifying versions or definition.
    Requires current status to be 'published'.
    """
    try:
        return pause_workflow(
            db=db,
            user_id=current_user.id,
            workflow_id=workflow_id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))



@router.post(
    "/{workflow_id}/execute",
    response_model=ExecutionDetail,
    status_code=http_status.HTTP_200_OK,
)
def execute_workflow_endpoint(
    workflow_id: int,
    payload: WorkflowExecutionRequest = WorkflowExecutionRequest(),
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Executes a published workflow synchronously using the connector-agnostic execution engine.
    Validates organization boundary and published workflow status.
    """
    try:
        execution = execute_workflow(
            db=db,
            workflow_id=workflow_id,
            trigger_data=payload.trigger_data,
            user_id=current_user.id,
            organization_id=organization_id,
        )
        return to_execution_detail(execution)
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/triggers/poll",
    status_code=http_status.HTTP_200_OK,
)
def run_poll_cycle_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Runs a trigger polling cycle for the authenticated user's organization.
    """
    from app.modules.workflows.service import _get_membership
    try:
        membership = _get_membership(db, current_user.id)
        return run_trigger_poll_cycle(db, organization_id=membership.organization_id)
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/{workflow_id}/poll",
    status_code=http_status.HTTP_200_OK,
)
def poll_workflow_endpoint(
    workflow_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Polls triggers and executes events for a specific published workflow.
    """
    from app.modules.workflows.service import _get_membership
    try:
        membership = _get_membership(db, current_user.id)
        workflow = db.scalar(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.organization_id == membership.organization_id,
            )
        )
        if not workflow:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return poll_workflow_trigger(db, workflow)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/{workflow_id}/executions",
    response_model=list[ExecutionSummary],
    status_code=http_status.HTTP_200_OK,
)
def list_workflow_executions_endpoint(
    workflow_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    status: str | None = Query(None, description="Filter by execution status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists execution history specifically for the given workflow.
    """
    from app.modules.workflows.execution_service import list_executions, to_execution_summary
    try:
        executions = list_executions(
            db=db,
            workflow_id=workflow_id,
            status_filter=status,
            user_id=current_user.id,
            organization_id=organization_id,
            limit=limit,
            offset=offset,
        )
        return [to_execution_summary(e) for e in executions]
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get(
    "/{workflow_id}/health",
    response_model=WorkflowHealthResponse,
    status_code=http_status.HTTP_200_OK,
)
def get_workflow_health_endpoint(
    workflow_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns derived reliability and operational health metrics for the workflow.
    """
    from app.modules.workflows.execution_service import get_workflow_health
    try:
        return get_workflow_health(
            db=db,
            workflow_id=workflow_id,
            user_id=current_user.id,
            organization_id=organization_id,
        )
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=http_status.HTTP_400_BAD_REQUEST, detail=str(err))
    except PermissionError as err:
        raise HTTPException(status_code=http_status.HTTP_403_FORBIDDEN, detail=str(err))





