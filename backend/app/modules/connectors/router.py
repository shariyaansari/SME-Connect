from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.modules.connectors.registry import get_catalog
from app.modules.connectors.schemas import (
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionUpdateRequest,
    ConnectorCatalogItemResponse,
)
from app.modules.connectors.service import (
    create_connection,
    delete_connection,
    get_connection,
    list_connections,
    test_connection_by_id,
    update_connection,
)

router = APIRouter(
    prefix="/connectors",
    tags=["Connectors"],
)


@router.get(
    "/catalog",
    response_model=list[ConnectorCatalogItemResponse],
)
def get_connectors_catalog():
    return get_catalog()


@router.get(
    "",
    response_model=list[ConnectionResponse],
)
def get_connections(
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return list_connections(
            db=db,
            user_id=current_user.id,
            organization_id=organization_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/{connection_id}",
    response_model=ConnectionResponse,
)
def get_connection_endpoint(
    connection_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return get_connection(
            db=db,
            user_id=current_user.id,
            connection_id=connection_id,
            organization_id=organization_id,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.post(
    "",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_connection_endpoint(
    data: ConnectionCreateRequest,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return create_connection(
            db=db,
            user_id=current_user.id,
            data=data,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/{connection_id}/test",
    response_model=ConnectionTestResponse,
)
def test_connection_endpoint(
    connection_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return test_connection_by_id(
            db=db,
            user_id=current_user.id,
            connection_id=connection_id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.put(
    "/{connection_id}",
    response_model=ConnectionResponse,
)
def update_connection_endpoint(
    connection_id: int,
    data: ConnectionUpdateRequest,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return update_connection(
            db=db,
            user_id=current_user.id,
            connection_id=connection_id,
            data=data,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_connection_endpoint(
    connection_id: int,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_connection(
            db=db,
            user_id=current_user.id,
            connection_id=connection_id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
