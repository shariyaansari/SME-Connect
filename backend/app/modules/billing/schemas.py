from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class PlanTierInfo(BaseModel):
    tier: str
    name: str
    description: str
    price_usd_monthly: float
    price_usd_annual: float
    price_inr_monthly: float
    price_inr_annual: float
    max_active_workflows: Optional[int] = None
    execution_limit: str = "unlimited"
    is_popular: bool = False
    features: List[str]


class PlanCatalogResponse(BaseModel):
    plans: List[PlanTierInfo]
    pricing_model: str = "flat_workflow_count"
    guarantee: str = (
        "Zero task-based metering. Run unlimited executions and tasks on all active workflows without unexpected costs."
    )


class UsageMetrics(BaseModel):
    active_workflows: int = Field(..., description="Currently published/active workflows count")
    paused_workflows: int = 0
    draft_workflows: int = 0
    total_workflows: int = 0
    max_active_workflows: Optional[int] = Field(
        None, description="Maximum allowed active workflows (None indicates unlimited)"
    )
    usage_percentage: float = Field(
        0.0, description="Percentage of active workflow limit consumed (0.0 to 100.0)"
    )
    is_limit_reached: bool = False
    remaining_slots: Optional[int] = None


class SubscriptionResponse(BaseModel):
    id: int
    organization_id: int
    plan_tier: str
    plan_name: str
    status: str
    billing_cycle: str
    current_period_start: datetime
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool
    created_at: datetime
    updated_at: datetime


class BillingOverviewResponse(BaseModel):
    subscription: SubscriptionResponse
    plan: PlanTierInfo
    usage: UsageMetrics
    pricing_model: str = "flat_workflow_count"
    can_manage_billing: bool = Field(
        ..., description="True if caller has Admin role in the organization"
    )


class SubscriptionUpdateRequest(BaseModel):
    plan_tier: str = Field(..., description="Target plan tier: free, starter, pro, or enterprise")
    billing_cycle: Optional[str] = Field("monthly", description="monthly or annual")


class SubscriptionCancelResponse(BaseModel):
    message: str
    cancel_at_period_end: bool
    current_period_end: Optional[datetime] = None
