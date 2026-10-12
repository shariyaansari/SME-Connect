from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Workflow, WorkflowExecution
from app.modules.monitoring.schemas import (
    DailyRunMetric,
    DashboardOverviewResponse,
    ExecutionMetricsSummary,
    MonthlyUsageResponse,
    WorkflowMonitoringItem,
    WorkflowStatusSummary,
    WorkflowUsageItem,
)
from app.modules.workflows.health import WorkflowHealthStatus, calculate_workflow_health


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_dashboard_overview(
    db: Session,
    organization_id: int,
    period_days: int = 30,
) -> DashboardOverviewResponse:
    """
    Computes an organization-level monitoring overview:
    - Workflow status counts (published, paused, draft, needs_attention)
    - Execution metrics (total, success, failed, success_rate, avg_duration)
    - Daily execution timeline over the chosen period
    - Enriched workflow health and performance items
    Strictly isolated to the organization.
    """
    now = _utc_now()
    cutoff = now - timedelta(days=max(1, min(period_days, 90)))
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # 1. Fetch workflows in organization
    workflows = list(
        db.scalars(
            select(Workflow)
            .where(Workflow.organization_id == organization_id)
            .order_by(Workflow.created_at.desc())
        ).all()
    )

    published_count = 0
    paused_count = 0
    draft_count = 0
    needs_attention_count = 0

    workflow_health_map: dict[int, tuple[str, str]] = {}
    for wf in workflows:
        if wf.status == "published":
            published_count += 1
        elif wf.status == "paused":
            paused_count += 1
        elif wf.status == "draft":
            draft_count += 1

        try:
            health = calculate_workflow_health(db, wf.id, organization_id)
            workflow_health_map[wf.id] = (health.health_status.value, health.health_message)
            if health.health_status == WorkflowHealthStatus.NEEDS_ATTENTION:
                needs_attention_count += 1
        except Exception:
            workflow_health_map[wf.id] = ("unknown", "Health unavailable")

    workflow_summary = WorkflowStatusSummary(
        total=len(workflows),
        published=published_count,
        paused=paused_count,
        draft=draft_count,
        needs_attention=needs_attention_count,
    )

    # 2. Fetch executions within period
    execs_in_period = list(
        db.scalars(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= cutoff,
            )
            .order_by(WorkflowExecution.created_at.asc())
        ).all()
    )

    total_runs = len(execs_in_period)
    successful_runs = sum(1 for e in execs_in_period if e.status == "success")
    failed_runs = sum(1 for e in execs_in_period if e.status == "failed")
    running_runs = sum(1 for e in execs_in_period if e.status in ("running", "pending"))

    success_rate = round((successful_runs / total_runs * 100.0), 2) if total_runs > 0 else 100.0

    durations: list[float] = []
    for e in execs_in_period:
        if e.started_at and e.completed_at:
            dur = (e.completed_at - e.started_at).total_seconds()
            if dur >= 0:
                durations.append(dur)
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

    execution_metrics = ExecutionMetricsSummary(
        total_runs=total_runs,
        successful_runs=successful_runs,
        failed_runs=failed_runs,
        running_runs=running_runs,
        success_rate=success_rate,
        avg_duration_seconds=avg_duration,
    )

    # 3. Build daily timeline
    daily_buckets: dict[str, dict[str, int]] = {}
    curr_date = cutoff.date()
    end_date = now.date()
    while curr_date <= end_date:
        d_str = curr_date.strftime("%Y-%m-%d")
        daily_buckets[d_str] = {"total": 0, "success": 0, "failed": 0}
        curr_date += timedelta(days=1)

    for e in execs_in_period:
        d_str = e.created_at.strftime("%Y-%m-%d")
        if d_str in daily_buckets:
            daily_buckets[d_str]["total"] += 1
            if e.status == "success":
                daily_buckets[d_str]["success"] += 1
            elif e.status == "failed":
                daily_buckets[d_str]["failed"] += 1

    timeline: list[DailyRunMetric] = []
    for d_str, counts in sorted(daily_buckets.items()):
        tot = counts["total"]
        succ = counts["success"]
        rate = round((succ / tot * 100.0), 2) if tot > 0 else 100.0
        timeline.append(
            DailyRunMetric(
                date=d_str,
                total=tot,
                success=succ,
                failed=counts["failed"],
                success_rate=rate,
            )
        )

    # 4. Month-to-date execution counts per workflow
    month_execs = list(
        db.scalars(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= start_of_month,
            )
        ).all()
    )
    month_counts_by_wf: dict[int, int] = {}
    for me in month_execs:
        month_counts_by_wf[me.workflow_id] = month_counts_by_wf.get(me.workflow_id, 0) + 1

    # 5. Enrich workflows
    # Group period executions by workflow for quick metrics
    period_execs_by_wf: dict[int, list[WorkflowExecution]] = {}
    for e in execs_in_period:
        period_execs_by_wf.setdefault(e.workflow_id, []).append(e)

    workflow_items: list[WorkflowMonitoringItem] = []
    for wf in workflows:
        wf_period_execs = period_execs_by_wf.get(wf.id, [])
        wf_tot = len(wf_period_execs)
        wf_succ = sum(1 for e in wf_period_execs if e.status == "success")
        wf_fail = sum(1 for e in wf_period_execs if e.status == "failed")
        wf_rate = round((wf_succ / wf_tot * 100.0), 2) if wf_tot > 0 else None

        # Latest execution for this workflow
        latest_exec = db.scalar(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == wf.id,
                WorkflowExecution.organization_id == organization_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(1)
        )

        h_status, h_msg = workflow_health_map.get(wf.id, ("unknown", "Status unavailable"))

        workflow_items.append(
            WorkflowMonitoringItem(
                id=wf.id,
                name=wf.name,
                status=wf.status,
                health_status=h_status,
                health_message=h_msg,
                total_runs=wf_tot,
                success_runs=wf_succ,
                failed_runs=wf_fail,
                success_rate=wf_rate,
                tasks_this_month=month_counts_by_wf.get(wf.id, 0),
                last_run_at=latest_exec.created_at if latest_exec else None,
                last_run_status=latest_exec.status if latest_exec else None,
                created_at=wf.created_at,
            )
        )

    return DashboardOverviewResponse(
        period_days=period_days,
        workflow_summary=workflow_summary,
        execution_metrics=execution_metrics,
        timeline=timeline,
        workflows=workflow_items,
    )


def get_monthly_usage_stats(
    db: Session,
    organization_id: int,
    year: int | None = None,
    month: int | None = None,
) -> MonthlyUsageResponse:
    """
    Computes month-to-date or specific month task execution counts per workflow.
    Guarantees strict tenant isolation.
    """
    now = _utc_now()
    target_year = year if year is not None else now.year
    target_month = month if month is not None else now.month

    start_of_month = datetime(target_year, target_month, 1, 0, 0, 0, tzinfo=timezone.utc)
    if target_month == 12:
        end_of_month = datetime(target_year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    else:
        end_of_month = datetime(target_year, target_month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # All workflows in org
    workflows = list(
        db.scalars(
            select(Workflow)
            .where(Workflow.organization_id == organization_id)
        ).all()
    )
    wf_name_map = {w.id: (w.name, w.status) for w in workflows}

    # Executions in target month
    execs = list(
        db.scalars(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= start_of_month,
                WorkflowExecution.created_at < end_of_month,
            )
            .order_by(WorkflowExecution.created_at.desc())
        ).all()
    )

    total_tasks = len(execs)
    total_successful = sum(1 for e in execs if e.status == "success")
    total_failed = sum(1 for e in execs if e.status == "failed")

    # Aggregate by workflow
    wf_stats: dict[int, dict] = {}
    for wf_id, (name, status) in wf_name_map.items():
        wf_stats[wf_id] = {
            "name": name,
            "status": status,
            "tasks": 0,
            "success": 0,
            "failed": 0,
            "last_executed_at": None,
        }

    for e in execs:
        if e.workflow_id not in wf_stats:
            wf_stats[e.workflow_id] = {
                "name": f"Workflow #{e.workflow_id}",
                "status": "unknown",
                "tasks": 0,
                "success": 0,
                "failed": 0,
                "last_executed_at": None,
            }
        entry = wf_stats[e.workflow_id]
        entry["tasks"] += 1
        if e.status == "success":
            entry["success"] += 1
        elif e.status == "failed":
            entry["failed"] += 1
        if entry["last_executed_at"] is None:
            entry["last_executed_at"] = e.created_at

    usage_items: list[WorkflowUsageItem] = []
    for wf_id, data in wf_stats.items():
        tasks = data["tasks"]
        pct = round((tasks / total_tasks * 100.0), 2) if total_tasks > 0 else 0.0
        usage_items.append(
            WorkflowUsageItem(
                workflow_id=wf_id,
                workflow_name=data["name"],
                status=data["status"],
                tasks_this_month=tasks,
                successful_tasks_this_month=data["success"],
                failed_tasks_this_month=data["failed"],
                percentage_of_total=pct,
                last_executed_at=data["last_executed_at"],
            )
        )

    # Sort items with highest usage first
    usage_items.sort(key=lambda x: x.tasks_this_month, reverse=True)

    period_dt = datetime(target_year, target_month, 1)
    period_label = period_dt.strftime("%B %Y")

    active_wf_count = sum(1 for u in usage_items if u.status == "published")

    return MonthlyUsageResponse(
        year=target_year,
        month=target_month,
        period_label=period_label,
        total_tasks_this_month=total_tasks,
        total_successful_tasks=total_successful,
        total_failed_tasks=total_failed,
        active_workflows_count=active_wf_count,
        workflow_usage=usage_items,
    )
