from typing import Any, Dict, List, Optional

PLAN_CATALOG: Dict[str, Dict[str, Any]] = {
    "free": {
        "tier": "free",
        "name": "Free",
        "description": "Essential workflow automation for getting started without risk",
        "price_usd_monthly": 0,
        "price_usd_annual": 0,
        "price_inr_monthly": 0,
        "price_inr_annual": 0,
        "max_active_workflows": 2,
        "execution_limit": "unlimited",
        "is_popular": False,
        "features": [
            "Up to 2 active published workflows",
            "Unlimited workflow executions / tasks",
            "Zero per-task charges or overages",
            "Standard connectors (Google Sheets, CRM, Email)",
            "Visual workflow builder & mapping engine",
            "Community support",
        ],
    },
    "starter": {
        "tier": "starter",
        "name": "Starter",
        "description": "For growing SMEs standardizing daily repetitive operational processes",
        "price_usd_monthly": 19,
        "price_usd_annual": 180,  # $15/mo billed annually
        "price_inr_monthly": 1499,
        "price_inr_annual": 14390,  # ~1199/mo billed annually
        "max_active_workflows": 5,
        "execution_limit": "unlimited",
        "is_popular": True,
        "features": [
            "Up to 5 active published workflows",
            "Unlimited workflow executions / tasks",
            "Zero task metering — budget with 100% predictability",
            "All connectors including Stripe Billing & QuickBooks",
            "Automated failure recovery & retry queue",
            "Standard email & chat support",
        ],
    },
    "pro": {
        "tier": "pro",
        "name": "Pro",
        "description": "For high-volume operations running multi-step business logic across departments",
        "price_usd_monthly": 49,
        "price_usd_annual": 468,  # $39/mo billed annually
        "price_inr_monthly": 3999,
        "price_inr_annual": 38390,  # ~3199/mo billed annually
        "max_active_workflows": 15,
        "execution_limit": "unlimited",
        "is_popular": False,
        "features": [
            "Up to 15 active published workflows",
            "Unlimited workflow executions / tasks",
            "Flat pricing — no penalty for transaction spikes",
            "Advanced data transformations & expression preview",
            "Real-time monitoring metrics & observability dashboard",
            "Priority support with guaranteed SLA",
        ],
    },
    "enterprise": {
        "tier": "enterprise",
        "name": "Enterprise",
        "description": "Unrestricted scale and dedicated integration assistance for established companies",
        "price_usd_monthly": 149,
        "price_usd_annual": 1428,  # $119/mo billed annually
        "price_inr_monthly": 11999,
        "price_inr_annual": 115190,  # ~9599/mo billed annually
        "max_active_workflows": None,  # Unlimited
        "execution_limit": "unlimited",
        "is_popular": False,
        "features": [
            "Unlimited active workflows",
            "Unlimited workflow executions / tasks",
            "Flat predictable pricing regardless of load",
            "Custom connector development & team onboarding",
            "Dedicated account manager",
            "24/7 dedicated support",
        ],
    },
}


def get_plan(tier: str) -> Optional[Dict[str, Any]]:
    return PLAN_CATALOG.get(tier.lower())


def get_all_plans() -> List[Dict[str, Any]]:
    return list(PLAN_CATALOG.values())
