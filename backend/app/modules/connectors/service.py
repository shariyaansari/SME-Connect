from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Connection, Membership
from app.modules.connectors.registry import get_adapter, is_valid_connector
from app.modules.connectors.schemas import (
    ConnectionCreateRequest,
    ConnectionResponse,
    ConnectionTestResponse,
    ConnectionUpdateRequest,
)


def mask_credentials(credentials: dict[str, Any] | None) -> dict[str, str]:
    if not credentials:
        return {}

    masked: dict[str, str] = {}
    for key, val in credentials.items():
        sval = str(val)
        if len(sval) <= 8:
            masked[key] = "••••••••"
        else:
            masked[key] = f"{sval[:3]}••••{sval[-3:]}"
    return masked


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


def _to_response(conn: Connection) -> ConnectionResponse:
    return ConnectionResponse(
        id=conn.id,
        organization_id=conn.organization_id,
        connector_slug=conn.connector_slug,
        name=conn.name,
        auth_type=conn.auth_type,
        config=conn.config or {},
        masked_credentials=mask_credentials(conn.credentials),
        status=conn.status,
        last_tested_at=conn.last_tested_at,
        error_message=conn.error_message,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


def list_connections(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> list[ConnectionResponse]:
    membership = _get_membership(db, user_id, organization_id)

    connections = db.scalars(
        select(Connection)
        .where(Connection.organization_id == membership.organization_id)
        .order_by(Connection.id.desc())
    ).all()

    return [_to_response(conn) for conn in connections]


def get_connection(
    db: Session,
    user_id: int,
    connection_id: int,
    organization_id: int | None = None,
) -> ConnectionResponse:
    membership = _get_membership(db, user_id, organization_id)

    connection = db.scalar(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.organization_id == membership.organization_id,
        )
    )
    if not connection:
        raise ValueError("Connection not found")

    return _to_response(connection)


def create_connection(
    db: Session,
    user_id: int,
    data: ConnectionCreateRequest,
    organization_id: int | None = None,
) -> ConnectionResponse:
    membership = _get_membership(db, user_id, organization_id)

    if membership.role not in {"Admin", "Editor"}:
        raise PermissionError("Only Admins and Editors can create connections")

    if not is_valid_connector(data.connector_slug):
        raise ValueError(f"Unknown connector slug: '{data.connector_slug}'")

    adapter = get_adapter(data.connector_slug)
    now = datetime.now(timezone.utc)

    # Perform initial connection health check
    success, message = adapter.test_connection(data.config, data.credentials)
    status = "active" if success else "error"
    error_msg = None if success else message

    connection = Connection(
        organization_id=membership.organization_id,
        connector_slug=data.connector_slug,
        name=data.name.strip(),
        auth_type=data.auth_type,
        config=data.config,
        credentials=data.credentials,
        status=status,
        last_tested_at=now,
        error_message=error_msg,
    )

    db.add(connection)
    db.commit()
    db.refresh(connection)

    return _to_response(connection)


def test_connection_by_id(
    db: Session,
    user_id: int,
    connection_id: int,
    organization_id: int | None = None,
) -> ConnectionTestResponse:
    membership = _get_membership(db, user_id, organization_id)

    if membership.role not in {"Admin", "Editor"}:
        raise PermissionError("Only Admins and Editors can test connections")

    connection = db.scalar(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.organization_id == membership.organization_id,
        )
    )
    if not connection:
        raise ValueError("Connection not found")

    adapter = get_adapter(connection.connector_slug)
    if not adapter:
        raise ValueError(f"No adapter available for {connection.connector_slug}")

    now = datetime.now(timezone.utc)
    success, message = adapter.test_connection(connection.config, connection.credentials)

    connection.status = "active" if success else "error"
    connection.last_tested_at = now
    connection.error_message = None if success else message

    db.commit()

    return ConnectionTestResponse(
        success=success,
        status=connection.status,
        message=message,
        tested_at=now,
    )


def update_connection(
    db: Session,
    user_id: int,
    connection_id: int,
    data: ConnectionUpdateRequest,
    organization_id: int | None = None,
) -> ConnectionResponse:
    membership = _get_membership(db, user_id, organization_id)

    if membership.role not in {"Admin", "Editor"}:
        raise PermissionError("Only Admins and Editors can update connections")

    connection = db.scalar(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.organization_id == membership.organization_id,
        )
    )
    if not connection:
        raise ValueError("Connection not found")

    if data.name is not None:
        connection.name = data.name.strip()

    if data.config is not None:
        new_config = dict(connection.config or {})
        new_config.update(data.config)
        connection.config = new_config

    if data.credentials is not None:
        new_creds = dict(connection.credentials or {})
        new_creds.update(data.credentials)
        connection.credentials = new_creds

    # Re-test connection
    adapter = get_adapter(connection.connector_slug)
    if adapter:
        now = datetime.now(timezone.utc)
        success, message = adapter.test_connection(connection.config, connection.credentials)
        connection.status = "active" if success else "error"
        connection.last_tested_at = now
        connection.error_message = None if success else message

    db.commit()
    db.refresh(connection)

    return _to_response(connection)


def delete_connection(
    db: Session,
    user_id: int,
    connection_id: int,
    organization_id: int | None = None,
) -> None:
    membership = _get_membership(db, user_id, organization_id)

    if membership.role not in {"Admin", "Editor"}:
        raise PermissionError("Only Admins and Editors can delete connections")

    connection = db.scalar(
        select(Connection).where(
            Connection.id == connection_id,
            Connection.organization_id == membership.organization_id,
        )
    )
    if not connection:
        raise ValueError("Connection not found")

    db.delete(connection)
    db.commit()
