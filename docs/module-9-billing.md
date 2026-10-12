# Module 9: Flat, Predictable Billing & Subscription

## 1. Overview & Market Rationale

A major inhibitor for SME automation adoption identified in market research is **unpredictable task-based metering**. Platforms like Zapier charge steeply when execution/task volumes spike ($19.99 to $100+/month), penalizing small and medium-sized businesses for scaling their operations and creating fear of "surprise bills."

**SME Connect closes this gap with a flat, workflow-count-based subscription model with unlimited execution runs:**
- Pricing scales exclusively by the **number of active (published) workflows**.
- Workflow executions and individual step tasks are **100% unmetered and unlimited**.
- Small businesses can budget with total predictability.
- Quotas are transparently surfaced in a dedicated usage dashboard.
- Upgrades and downgrades are self-serve without requiring sales calls.

---

## 2. Subscription Tiers & Quota Catalog

| Plan Tier | Price (USD) | Price (INR) | Active Workflows Quota | Executions / Tasks | Support | Target SME Profile |
|---|---|---|---|---|---|---|
| **Free** | $0 / mo | ₹0 / mo | **2 active workflows** | Unlimited & Unmetered | Community | Getting started without financial risk |
| **Starter** | $19 / mo ($15/mo billed annually) | ₹1,499 / mo (₹1,199/mo billed annually) | **5 active workflows** | Unlimited & Unmetered | Standard Email & Chat | Growing SMEs standardizing daily repetitive operations |
| **Pro** | $49 / mo ($39/mo billed annually) | ₹3,999 / mo (₹3,199/mo billed annually) | **15 active workflows** | Unlimited & Unmetered | Priority Email with SLA | High-volume operational teams running multi-step processes |
| **Enterprise** | $149 / mo ($119/mo billed annually) | ₹11,999 / mo (₹9,599/mo billed annually) | **Unlimited active workflows** | Unlimited & Unmetered | 24/7 Dedicated Support | Established businesses requiring custom scale and onboarding |

*All paid tiers include a 20% discount when billed annually.*

---

## 3. Workflow Limit Enforcement Semantics

### Quota Enforcement Point
The quota is enforced at the workflow publication lifecycle in `app.modules.workflows.service.publish_workflow`:
1. When a user calls `POST /workflows/{id}/publish`:
   - The system retrieves the organization's current subscription tier.
   - It counts all other workflows currently in `status == "published"` within that organization.
   - If `current_published_count >= max_active_workflows`, publishing is rejected with **HTTP 402 Payment Required**:
     ```json
     {
       "detail": "Plan limit reached: You have reached the maximum of 2 active workflows for the 'Free' plan. Upgrade your subscription to activate more workflows without per-task charges."
     }
     ```
2. **Pausing Workflows Frees Quota**:
   - Calling `POST /workflows/{id}/pause` transitions a workflow to `"paused"`.
   - Paused workflows do not consume active quota slots, immediately allowing another workflow to be published.
3. **Draft Workflows**:
   - Creating or editing draft workflows is unmetered across all plans.

---

## 4. API Specifications

### `GET /billing/plans`
Returns the public plan catalog with flat workflow limits and feature guarantees.
- **Authentication**: Public or Authenticated
- **Response**:
  ```json
  {
    "pricing_model": "flat_workflow_count",
    "guarantee": "Zero task-based metering. Run unlimited executions and tasks on all active workflows without unexpected costs.",
    "plans": [
      {
        "tier": "free",
        "name": "Free",
        "description": "Essential workflow automation for getting started without risk",
        "price_usd_monthly": 0.0,
        "price_usd_annual": 0.0,
        "price_inr_monthly": 0.0,
        "price_inr_annual": 0.0,
        "max_active_workflows": 2,
        "execution_limit": "unlimited",
        "is_popular": false,
        "features": [...]
      },
      ...
    ]
  }
  ```

### `GET /billing/subscription`
Returns the caller's organization subscription, usage metrics, and quota utilization.
- **Query Parameter**: `organization_id` (optional, defaults to primary org)
- **Response**:
  ```json
  {
    "subscription": {
      "id": 1,
      "organization_id": 10,
      "plan_tier": "starter",
      "plan_name": "Starter",
      "status": "active",
      "billing_cycle": "annual",
      "current_period_start": "2026-10-12T16:00:00Z",
      "current_period_end": "2027-10-12T16:00:00Z",
      "cancel_at_period_end": false,
      "created_at": "2026-10-12T16:00:00Z",
      "updated_at": "2026-10-12T16:00:00Z"
    },
    "plan": { ... },
    "usage": {
      "active_workflows": 3,
      "paused_workflows": 1,
      "draft_workflows": 2,
      "total_workflows": 6,
      "max_active_workflows": 5,
      "usage_percentage": 60.0,
      "is_limit_reached": false,
      "remaining_slots": 2
    },
    "pricing_model": "flat_workflow_count",
    "can_manage_billing": true
  }
  ```

### `POST /billing/subscription`
Upgrades or downgrades the organization's subscription tier.
- **Permissions**: Requires `Admin` organization role.
- **Request Body**:
  ```json
  {
    "plan_tier": "pro",
    "billing_cycle": "monthly"
  }
  ```
- **Response**: Updated `BillingOverviewResponse`.
- **Side Effects**: Logs `subscription.updated` event in `AuditLog`.

### `POST /billing/cancel`
Schedules subscription cancellation at the end of the billing period.
- **Permissions**: Requires `Admin` organization role.
- **Response**:
  ```json
  {
    "message": "Subscription for plan 'Pro' is scheduled to cancel at the end of the billing period.",
    "cancel_at_period_end": true,
    "current_period_end": "2026-11-12T16:00:00Z"
  }
  ```
- **Side Effects**: Logs `subscription.canceled` event in `AuditLog`.

---

## 5. Database Schema & Multi-Tenancy

### `subscriptions` Table
Mapped through `Subscription` in `app.database.models`:

| Column | Type | Constraints / Defaults | Description |
|---|---|---|---|
| `id` | Integer | Primary Key | Subscription ID |
| `organization_id` | Integer | ForeignKey(`organizations.id`), Unique, Index | Scoped organization |
| `plan_tier` | String(50) | Default `"free"`, Not Null | `free`, `starter`, `pro`, `enterprise` |
| `status` | String(50) | Default `"active"`, Not Null | `active`, `canceled`, `past_due` |
| `billing_cycle` | String(20) | Default `"monthly"`, Not Null | `monthly`, `annual` |
| `current_period_start` | DateTime(tz) | Default `utc_now`, Not Null | Period start date |
| `current_period_end` | DateTime(tz) | Nullable | Period renewal/end date |
| `cancel_at_period_end` | Boolean | Default `False`, Not Null | Scheduled cancellation flag |
| `created_at` | DateTime(tz) | Default `utc_now`, Not Null | Creation timestamp |
| `updated_at` | DateTime(tz) | Default `utc_now`, OnUpdate `utc_now` | Last update timestamp |

### Multi-Tenancy & RBAC Isolation
- Organizations default seamlessly to the `"free"` plan if no explicit subscription row exists.
- All usage queries strictly filter by `organization_id`.
- Quota exhaustion in Organization A has zero impact on Organization B.
- Non-Admin members (`Editor`, `Viewer`) can inspect plan usage but receive **HTTP 403 Forbidden** when attempting mutations.

---

## 6. Frontend Components & User Experience

1. **`BillingView.jsx`**:
   - **Guarantee Banner**: Highlights the "Zero per-task charges & unlimited executions" differentiator.
   - **Usage Meter**: Visual progress bar showing active workflows used, remaining capacity, and status badges (`Quota Reached`, `Near Quota`, `Healthy`).
   - **Plan Cards**: Interactive comparison matrix for Free, Starter, Pro, and Enterprise tiers with Monthly/Annual toggles (-20% savings badge) and USD/INR currency switches.
   - **Plan Switch Confirmation Modal**: Explains immediate quota changes and confirms billing rate.
   - **Role-Aware UI**: Non-Admin members see "Admin required" buttons with helpful tooltips.
2. **Navigation Header (`Header.jsx` & `App.jsx`)**:
   - Integrated "Billing & plans" top-level tab.
3. **Workflow Builder Integration (`WorkflowsView.jsx`)**:
   - When a user tries to publish a workflow and exceeds their plan limit, an inline alert displays the exact error detail alongside a direct **"View Plans & Upgrade"** action button.

---

## 7. Automated Test Suite & Verification Results

The test suite in `backend/tests/test_module9_billing.py` executes 7 end-to-end integration test scenarios:
1. `test_get_plan_catalog`: Validates public catalog schema, tiers, quotas, and zero-metering guarantee.
2. `test_default_subscription_and_usage_metrics`: Verifies default Free tier initialization and initial 0% usage.
3. `test_workflow_publish_limit_enforcement`: Confirms publishing 1st and 2nd workflow succeeds, 3rd workflow is blocked with HTTP 402, pausing workflow 1 frees quota, and workflow 3 publishes cleanly.
4. `test_self_serve_upgrade_and_quota_expansion`: Tests admin upgrade from Free (2) to Starter (5) and Enterprise (unlimited), expanding quotas instantly.
5. `test_billing_rbac_permissions`: Validates that Editors and Viewers can view billing but are blocked with HTTP 403 when attempting modifications.
6. `test_multitenant_quota_isolation`: Confirms Organization A's quota exhaustion does not impact Organization B.
7. `test_subscription_cancellation_and_audit_trail`: Verifies cancellation lifecycle and audit log recording (`subscription.updated`, `subscription.canceled`).

### Test Results
- **Module 9 Tests**: 7 / 7 passed.
- **Full Backend Suite**: 186 / 186 passed with 0 regressions.
- **Frontend Build**: Vite production bundle compiled in 646ms with 0 errors.
