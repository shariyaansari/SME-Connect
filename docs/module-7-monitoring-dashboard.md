# Module 7: Monitoring Dashboard & Notifications

## 1. Purpose & Overview

Module 7 is the **Trust and Observability Layer** of SME Connect. Non-technical SME business owners and managers need transparent, verifiable proof that automated workflows are running properly, without having to inspect raw database tables, server logs, or third-party webhooks.

This module provides:
1. **Workflow Status Overview**: Real-time operational statuses (`published/active`, `paused`, `draft`, `needs_attention`).
2. **Run History & Reliability Metrics**: Consolidated success/failure rates, execution volumes, and visual daily timelines over configurable horizons (7, 14, 30 days).
3. **Automated Repeated Failure Notifications**: Proactive in-app alerting when a workflow encounters repeated failures (consecutive failures $\ge 2$), enriched with plain-language diagnostics and recommended corrective actions.
4. **Monthly Task Usage Tracking**: Month-to-date execution counters at both the workspace and individual workflow levels to manage usage throughput and plan limits.

---

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────┐
│                   FRONTEND / WEB UI                   │
│                                                        │
│  [Monitoring Dashboard]         [Notification Bell]   │
│   - KPI Summary Cards            - Unread Badge Counter│
│   - Performance Timeline         - Alert Popover List  │
│   - Automations Health Table     - Mark Read / Dismiss │
│   - Monthly Usage Breakdown                            │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
         HTTP GET /monitoring    HTTP /notifications
                │                        │
┌───────────────▼────────────────────────▼───────────────┐
│                   BACKEND API (FastAPI)                │
│                                                        │
│  ┌─────────────────────────┐  ┌──────────────────────┐ │
│  │ app.modules.monitoring  │  │ app.modules.         │ │
│  │  - Dashboard Service    │  │   notifications      │ │
│  │  - Usage Metrics        │  │  - Notification Svc │ │
│  └────────────┬────────────┘  └──────────┬───────────┘ │
│               │                          │             │
│               │             check_and_notify_          │
│               │             repeated_failure           │
│               │                          ▲             │
│               ▼                          │             │
│  ┌────────────────────────┐  ┌───────────┴───────────┐ │
│  │  workflows / executions│◄─┤   executions/service  │ │
│  └────────────┬───────────┘  └───────────────────────┘ │
└───────────────┼────────────────────────────────────────┘
                ▼
┌────────────────────────────────────────────────────────┐
│                   PERSISTENCE (DB)                     │
│                                                        │
│  - workflows             - workflow_executions         │
│  - notifications         - memberships (RBAC/Tenant)   │
└────────────────────────────────────────────────────────┘
```

---

## 3. API Specifications

### 3.1 Monitoring Endpoints (`/monitoring`)

#### `GET /monitoring/dashboard`
Returns high-level operational metrics, status summaries, daily timeline trends, and enriched workflow health items.
- **Query Parameters**:
  - `period_days` (*int*, default: 30, range: 1–90): Time window in days.
  - `organization_id` (*int*, optional): Target organization ID (verified against caller membership).
- **Response Contract (`DashboardOverviewResponse`)**:
```json
{
  "period_days": 30,
  "workflow_summary": {
    "total": 4,
    "published": 2,
    "paused": 1,
    "draft": 1,
    "needs_attention": 1
  },
  "execution_metrics": {
    "total_runs": 84,
    "successful_runs": 78,
    "failed_runs": 6,
    "running_runs": 0,
    "success_rate": 92.86,
    "avg_duration_seconds": 1.15
  },
  "timeline": [
    {
      "date": "2026-10-10",
      "total": 12,
      "success": 11,
      "failed": 1,
      "success_rate": 91.67
    }
  ],
  "workflows": [
    {
      "id": 1,
      "name": "Customer Lead Sync",
      "status": "published",
      "health_status": "healthy",
      "health_message": "Operating normally",
      "total_runs": 45,
      "success_runs": 44,
      "failed_runs": 1,
      "success_rate": 97.78,
      "tasks_this_month": 45,
      "last_run_at": "2026-10-12T14:22:00Z",
      "last_run_status": "success",
      "created_at": "2026-10-01T10:00:00Z"
    }
  ]
}
```

#### `GET /monitoring/usage`
Returns month-to-date or calendar month throughput breakdown.
- **Query Parameters**:
  - `year` (*int*, optional): Target calendar year (e.g. 2026).
  - `month` (*int*, optional): Target month (1–12).
  - `organization_id` (*int*, optional): Target organization ID.
- **Response Contract (`MonthlyUsageResponse`)**:
```json
{
  "year": 2026,
  "month": 10,
  "period_label": "October 2026",
  "total_tasks_this_month": 120,
  "total_successful_tasks": 112,
  "total_failed_tasks": 8,
  "active_workflows_count": 3,
  "workflow_usage": [
    {
      "workflow_id": 1,
      "workflow_name": "Customer Lead Sync",
      "status": "published",
      "tasks_this_month": 75,
      "successful_tasks_this_month": 72,
      "failed_tasks_this_month": 3,
      "percentage_of_total": 62.5,
      "last_executed_at": "2026-10-12T14:30:00Z"
    }
  ]
}
```

#### `GET /monitoring/workflows`
Returns detailed monitoring items for all organization workflows.
- **Query Parameters**: `period_days` (*int*), `organization_id` (*int*, optional).
- **Response Contract**: `list[WorkflowMonitoringItem]`.

---

### 3.2 Notification Endpoints (`/notifications`)

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `GET` | `/notifications` | List paginated notifications (`is_read`, `limit`, `offset`) | Viewer, Editor, Admin |
| `GET` | `/notifications/unread-count` | Get count of unread notifications | Viewer, Editor, Admin |
| `PATCH`| `/notifications/{id}/read` | Mark single notification as read | Viewer, Editor, Admin |
| `POST` | `/notifications/mark-all-read` | Mark all workspace notifications as read | Viewer, Editor, Admin |
| `DELETE`| `/notifications/{id}` | Dismiss / delete notification | Editor, Admin |

---

## 4. Automated Repeated Failure Detection

### 4.1 Trigger Condition
Whenever an execution fails (step execution exception or unhandled runner exception) inside `execute_workflow`, the execution engine invokes:
```python
check_and_notify_repeated_failure(
    db=db,
    workflow_id=workflow.id,
    execution_id=execution.id,
    organization_id=execution.organization_id,
    threshold=2,
)
```

### 4.2 Deduplication & Anti-Spam Logic
1. Evaluates the most recent executions for the workflow in descending timestamp order.
2. Counts consecutive failures starting from the latest execution.
3. If `consecutive_failures < 2`: No alert is generated (transient single failures are handled by automatic retry policies).
4. If `consecutive_failures >= 2`:
   - Checks if an **unread** notification of type `repeated_failure` already exists for this workflow.
   - If an unread alert exists: **Updates in place** (increments failure count in title, refreshes timestamp and diagnostic message).
   - If no unread alert exists: Creates a new `Notification` record.
   - Escalates severity from `warning` to `critical` once consecutive failures reach 3 or more.
5. Notification diagnostics use `explain_failure_for_user` to provide plain-language explanations and recommended actions rather than raw tracebacks.

---

## 5. Security, Authorization & Multi-Tenancy

- **Organization-Level Isolation**: Every query resolves caller membership via `_get_membership`. Cross-organization requests return `404 Not Found`.
- **Role-Based Access Control**:
  - `Viewer`: Can view dashboard metrics, performance timelines, usage stats, and notifications.
  - `Editor` / `Admin`: Can trigger manual workflow runs, retry failed executions, and dismiss/delete alerts.
- **Credential Protection**: Redaction and sanitization ensure API credentials, access tokens, and webhook secrets are strictly omitted from all monitoring and notification payloads.

---

## 6. Verification and Testing

### 6.1 Automated Backend Suite
Execute the dedicated Module 7 test suite:
```bash
pytest tests/test_module7_monitoring_dashboard.py
```
Coverage includes:
- Dashboard metrics calculation and empty-state handling.
- Timeline bucket distribution and success rate accuracy.
- Monthly task usage and per-workflow percentage calculations.
- Repeated failure threshold detection (consecutive failure $\ge 2$).
- Notification deduplication and in-place updates without spam.
- In-app notification read and delete lifecycle.
- Multi-tenant data isolation and RBAC constraints.

Execute the complete regression suite:
```bash
pytest
```
Expected result: **160 tests passing**.

### 6.2 Frontend Verification
Build the client application:
```bash
cd frontend && npm run build
```
Expected result: Clean Vite build with zero compilation errors.
