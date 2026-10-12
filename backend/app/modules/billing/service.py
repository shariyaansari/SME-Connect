import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Membership, Organization, Subscription, Workflow, utc_now
from app.modules.audit.service import create_audit_log
from app.modules.billing.catalog import PLAN_CATALOG, get_plan, get_all_plans
from app.modules.billing.schemas import (
    BillingOverviewResponse,
    PlanCatalogResponse,
    PlanTierInfo,
    SubscriptionCancelResponse,
    SubscriptionResponse,
    SubscriptionUpdateRequest,
    UsageMetrics,
)


class BillingLimitExceededError(ValueError):
    """Raised when an action would exceed the current subscription plan limit."""
    pass


def _get_membership(
    db: Session,
    user_id: int,
    organization_id: Optional[int] = None,
) -> Membership:
    """Verifies that the user is a member of the specified organization or their primary organization."""
    query = select(Membership).where(Membership.user_id == user_id)
    if organization_id is not None:
        query = query.where(Membership.organization_id == organization_id)

    membership = db.scalar(query)
    if not membership:
        raise PermissionError("User is not a member of this organization")
    return membership


def get_or_create_subscription(db: Session, organization_id: int) -> Subscription:
    """
    Retrieves the organization's subscription record, creating a default Free subscription
    if one does not already exist.
    """
    subscription = db.scalar(
        select(Subscription).where(Subscription.organization_id == organization_id)
    )

    if not subscription:
        now = utc_now()
        subscription = Subscription(
            organization_id=organization_id,
            plan_tier="free",
            status="active",
            billing_cycle="monthly",
            current_period_start=now,
            current_period_end=None,
            cancel_at_period_end=False,
            created_at=now,
            updated_at=now,
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    return subscription


def check_workflow_publish_limit(
    db: Session,
    organization_id: int,
    target_workflow_id: int,
) -> None:
    """
    Enforces the flat subscription limit on active published workflows.

    If publishing target_workflow_id causes active workflows to exceed
    the plan's max_active_workflows quota, raises BillingLimitExceededError.
    """
    subscription = get_or_create_subscription(db, organization_id)
    plan = get_plan(subscription.plan_tier) or PLAN_CATALOG["free"]

    max_active = plan.get("max_active_workflows")
    # Enterprise or unlimited plans have max_active == None
    if max_active is None:
        return

    # Count published workflows in this organization excluding the current target_workflow_id
    current_active_count = db.scalar(
        select(func.count(Workflow.id)).where(
            Workflow.organization_id == organization_id,
            Workflow.status == "published",
            Workflow.id != target_workflow_id,
        )
    ) or 0

    if current_active_count >= max_active:
        plan_name = plan.get("name", subscription.plan_tier.capitalize())
        raise BillingLimitExceededError(
            f"Plan limit reached: You have reached the maximum of {max_active} active workflows for the '{plan_name}' plan. "
            f"Upgrade your subscription to activate more workflows without per-task charges."
        )


def get_billing_usage(db: Session, organization_id: int) -> UsageMetrics:
    """Computes real-time workflow usage metrics for the given organization."""
    subscription = get_or_create_subscription(db, organization_id)
    plan = get_plan(subscription.plan_tier) or PLAN_CATALOG["free"]
    max_active = plan.get("max_active_workflows")

    published_count = db.scalar(
        select(func.count(Workflow.id)).where(
            Workflow.organization_id == organization_id,
            Workflow.status == "published",
        )
    ) or 0

    paused_count = db.scalar(
        select(func.count(Workflow.id)).where(
            Workflow.organization_id == organization_id,
            Workflow.status == "paused",
        )
    ) or 0

    draft_count = db.scalar(
        select(func.count(Workflow.id)).where(
            Workflow.organization_id == organization_id,
            Workflow.status == "draft",
        )
    ) or 0

    total_count = published_count + paused_count + draft_count

    if max_active is None:
        usage_pct = 0.0
        is_limit_reached = False
        remaining = None
    else:
        usage_pct = round(min(100.0, (published_count / max_active) * 100.0), 1) if max_active > 0 else 100.0
        is_limit_reached = published_count >= max_active
        remaining = max(0, max_active - published_count)

    return UsageMetrics(
        active_workflows=published_count,
        paused_workflows=paused_count,
        draft_workflows=draft_count,
        total_workflows=total_count,
        max_active_workflows=max_active,
        usage_percentage=usage_pct,
        is_limit_reached=is_limit_reached,
        remaining_slots=remaining,
    )


def get_billing_overview(
    db: Session,
    user_id: int,
    organization_id: Optional[int] = None,
) -> BillingOverviewResponse:
    """Returns complete subscription, plan specs, usage meters, and user permissions."""
    membership = _get_membership(db, user_id, organization_id)
    org_id = membership.organization_id

    subscription = get_or_create_subscription(db, org_id)
    plan_dict = get_plan(subscription.plan_tier) or PLAN_CATALOG["free"]
    plan_info = PlanTierInfo(**plan_dict)
    usage = get_billing_usage(db, org_id)

    sub_response = SubscriptionResponse(
        id=subscription.id,
        organization_id=subscription.organization_id,
        plan_tier=subscription.plan_tier,
        plan_name=plan_info.name,
        status=subscription.status,
        billing_cycle=subscription.billing_cycle,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
    )

    return BillingOverviewResponse(
        subscription=sub_response,
        plan=plan_info,
        usage=usage,
        can_manage_billing=(membership.role == "Admin"),
    )


def update_subscription(
    db: Session,
    user_id: int,
    request: SubscriptionUpdateRequest,
    organization_id: Optional[int] = None,
) -> BillingOverviewResponse:
    """
    Self-serve upgrade or downgrade of the organization subscription tier.
    Requires Admin membership role.
    """
    membership = _get_membership(db, user_id, organization_id)
    if membership.role != "Admin":
        raise PermissionError("Only organization Admins can change subscription plans")

    target_tier = request.plan_tier.lower()
    target_plan = get_plan(target_tier)
    if not target_plan:
        raise ValueError(
            f"Invalid plan tier '{request.plan_tier}'. Available tiers: {list(PLAN_CATALOG.keys())}"
        )

    billing_cycle = (request.billing_cycle or "monthly").lower()
    if billing_cycle not in ("monthly", "annual"):
        raise ValueError("Billing cycle must be either 'monthly' or 'annual'")

    org_id = membership.organization_id
    subscription = get_or_create_subscription(db, org_id)
    old_tier = subscription.plan_tier

    now = utc_now()
    if billing_cycle == "annual":
        period_end = now + timedelta(days=365)
    else:
        period_end = now + timedelta(days=30)

    subscription.plan_tier = target_tier
    subscription.billing_cycle = billing_cycle
    subscription.status = "active"
    subscription.cancel_at_period_end = False
    subscription.current_period_start = now
    subscription.current_period_end = period_end
    subscription.updated_at = now

    db.commit()
    db.refresh(subscription)

    # Record in AuditLog
    create_audit_log(
        db=db,
        organization_id=org_id,
        user_id=user_id,
        action="subscription.updated",
        resource_type="subscription",
        resource_id=subscription.id,
        details=json.dumps({
            "old_tier": old_tier,
            "new_tier": target_tier,
            "billing_cycle": billing_cycle,
        }),
    )
    db.commit()

    return get_billing_overview(db, user_id, org_id)


def cancel_subscription(
    db: Session,
    user_id: int,
    organization_id: Optional[int] = None,
) -> SubscriptionCancelResponse:
    """
    Schedules cancellation of the organization subscription at period end.
    Requires Admin membership role.
    """
    membership = _get_membership(db, user_id, organization_id)
    if membership.role != "Admin":
        raise PermissionError("Only organization Admins can cancel subscriptions")

    org_id = membership.organization_id
    subscription = get_or_create_subscription(db, org_id)

    subscription.cancel_at_period_end = True
    subscription.updated_at = utc_now()
    db.commit()
    db.refresh(subscription)

    create_audit_log(
        db=db,
        organization_id=org_id,
        user_id=user_id,
        action="subscription.canceled",
        resource_type="subscription",
        resource_id=subscription.id,
        details=json.dumps({
            "plan_tier": subscription.plan_tier,
            "cancel_at_period_end": True,
        }),
    )
    db.commit()

    return SubscriptionCancelResponse(
        message=f"Subscription for plan '{subscription.plan_tier.capitalize()}' is scheduled to cancel at the end of the billing period.",
        cancel_at_period_end=True,
        current_period_end=subscription.current_period_end,
    )
