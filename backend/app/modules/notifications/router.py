from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import Membership, User
from app.modules.notifications.schemas import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.modules.notifications.service import (
    delete_notification,
    get_unread_count,
    list_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
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
    response_model=NotificationListResponse,
)
def list_notifications_endpoint(
    is_read: bool | None = Query(None, description="Filter by read status"),
    limit: int = Query(50, ge=1, le=200, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    organization_id: int | None = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns paginated notifications for the organization, enriched with workflow names.
    Supports filtering by read/unread status.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        items, total, unread = list_notifications(
            db=db,
            organization_id=membership.organization_id,
            is_read=is_read,
            limit=limit,
            offset=offset,
        )
        return NotificationListResponse(
            items=[NotificationResponse(**item) for item in items],
            total=total,
            unread_count=unread,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
)
def get_unread_count_endpoint(
    organization_id: int | None = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns unread notification count for the organization.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        count = get_unread_count(db=db, organization_id=membership.organization_id)
        return UnreadCountResponse(unread_count=count)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_as_read_endpoint(
    notification_id: int,
    organization_id: int | None = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marks a single notification as read.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        notif = mark_notification_as_read(
            db=db,
            notification_id=notification_id,
            organization_id=membership.organization_id,
        )
        workflow_name = notif.workflow.name if notif.workflow else None
        return NotificationResponse(
            id=notif.id,
            organization_id=notif.organization_id,
            workflow_id=notif.workflow_id,
            workflow_name=workflow_name,
            execution_id=notif.execution_id,
            title=notif.title,
            message=notif.message,
            severity=notif.severity,
            notification_type=notif.notification_type,
            is_read=notif.is_read,
            created_at=notif.created_at,
            read_at=notif.read_at,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )


@router.post(
    "/mark-all-read",
    response_model=dict[str, int],
)
def mark_all_as_read_endpoint(
    organization_id: int | None = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Marks all notifications for the organization as read.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        count = mark_all_notifications_as_read(db=db, organization_id=membership.organization_id)
        return {"marked_read_count": count}
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.delete(
    "/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_notification_endpoint(
    notification_id: int,
    organization_id: int | None = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes / dismisses a notification.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        if membership.role == "Viewer":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewers cannot delete notifications",
            )
        delete_notification(
            db=db,
            notification_id=notification_id,
            organization_id=membership.organization_id,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        )
