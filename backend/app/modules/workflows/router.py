from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.modules.workflows.schemas import (
    ConnectorCapabilityResponse,
    WorkflowCreateRequest,
    WorkflowDetailResponse,
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
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_endpoint(
    data: WorkflowCreateRequest,
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
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except WorkflowValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in err.errors],
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get(
    "",
    response_model=list[WorkflowSummaryResponse],
)
def list_workflows_endpoint(
    status: str | None = Query(None, description="Optional filter by status (draft, published, paused)"),
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
            status_filter=status,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDetailResponse,
)
def get_workflow_endpoint(
    workflow_id: int,
    version: int | None = Query(None, description="Optional specific version number"),
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
            version_number=version,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.put(
    "/{workflow_id}",
    response_model=WorkflowDetailResponse,
)
def update_workflow_endpoint(
    workflow_id: int,
    data: WorkflowUpdateRequest,
    version: int | None = Query(None, description="Optional target version number to edit"),
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
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except WorkflowValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in err.errors],
        )
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete(
    "/{workflow_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_workflow_endpoint(
    workflow_id: int,
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
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "/{workflow_id}/publish",
    response_model=WorkflowDetailResponse,
)
def publish_workflow_endpoint(
    workflow_id: int,
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
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except WorkflowValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[e.model_dump() for e in err.errors],
        )
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/{workflow_id}/pause",
    response_model=WorkflowDetailResponse,
)
def pause_workflow_endpoint(
    workflow_id: int,
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
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        if "not found" in str(err).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

