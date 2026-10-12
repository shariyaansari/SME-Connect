from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.modules.billing.catalog import get_all_plans
from app.modules.billing.schemas import (
    BillingOverviewResponse,
    PlanCatalogResponse,
    PlanTierInfo,
    SubscriptionCancelResponse,
    SubscriptionUpdateRequest,
)
from app.modules.billing.service import (
    cancel_subscription,
    get_billing_overview,
    update_subscription,
)

router = APIRouter(
    prefix="/billing",
    tags=["Billing & Subscription"],
)


@router.get(
    "/plans",
    response_model=PlanCatalogResponse,
)
def get_plans():
    """
    Returns the complete SME Connect flat pricing plan catalog.
    Pricing is based on active workflow count, never on task executions.
    """
    plans = [PlanTierInfo(**p) for p in get_all_plans()]
    return PlanCatalogResponse(plans=plans)


@router.get(
    "/subscription",
    response_model=BillingOverviewResponse,
)
def get_subscription(
    organization_id: Optional[int] = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the organization's current subscription, plan limits, active workflow count,
    and usage percentage.
    """
    try:
        return get_billing_overview(
            db=db,
            user_id=current_user.id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/subscription",
    response_model=BillingOverviewResponse,
)
def change_subscription(
    request: SubscriptionUpdateRequest,
    organization_id: Optional[int] = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Self-serve upgrade or downgrade of the organization subscription tier.
    Requires Admin membership role.
    """
    try:
        return update_subscription(
            db=db,
            user_id=current_user.id,
            request=request,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post(
    "/cancel",
    response_model=SubscriptionCancelResponse,
)
def cancel_org_subscription(
    organization_id: Optional[int] = Query(None, description="Target organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Schedules cancellation of the organization subscription at period end.
    Requires Admin membership role.
    """
    try:
        return cancel_subscription(
            db=db,
            user_id=current_user.id,
            organization_id=organization_id,
        )
    except PermissionError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
