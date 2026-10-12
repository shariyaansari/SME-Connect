from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import Membership, User
from app.modules.monitoring.schemas import (
    DashboardOverviewResponse,
    MonthlyUsageResponse,
    WorkflowMonitoringItem,
)
from app.modules.monitoring.service import (
    get_dashboard_overview,
    get_monthly_usage_stats,
)

router = APIRouter(
    prefix="/monitoring",
    tags=["Monitoring"],
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
    "/dashboard",
    response_model=DashboardOverviewResponse,
)
def get_dashboard_endpoint(
    period_days: int = Query(30, ge=1, le=90, description="Horizon in days (e.g. 7, 14, 30)"),
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns high-level operational monitoring dashboard data:
    - Workflow status summary (active/paused/draft/needs attention)
    - Consolidated execution metrics and success rate
    - Daily run volume timeline
    - Per-workflow health and execution overview
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        return get_dashboard_overview(
            db=db,
            organization_id=membership.organization_id,
            period_days=period_days,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/usage",
    response_model=MonthlyUsageResponse,
)
def get_monthly_usage_endpoint(
    year: int | None = Query(None, ge=2000, le=2100, description="Target year"),
    month: int | None = Query(None, ge=1, le=12, description="Target month (1-12)"),
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns monthly task usage metrics:
    - Total tasks run this month
    - Success/failed breakdown
    - Per-workflow task consumption and percentage share
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        return get_monthly_usage_stats(
            db=db,
            organization_id=membership.organization_id,
            year=year,
            month=month,
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))


@router.get(
    "/workflows",
    response_model=list[WorkflowMonitoringItem],
)
def get_workflows_overview_endpoint(
    period_days: int = Query(30, ge=1, le=90, description="Period in days"),
    organization_id: int | None = Query(None, description="Optional target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns detailed monitoring and health states for all organization workflows.
    """
    try:
        membership = _get_membership(db, current_user.id, organization_id)
        overview = get_dashboard_overview(
            db=db,
            organization_id=membership.organization_id,
            period_days=period_days,
        )
        return overview.workflows
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(err))
