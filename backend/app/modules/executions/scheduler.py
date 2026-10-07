from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Workflow, WorkflowExecution, WorkflowTriggerState, WorkflowVersion
from app.modules.executions.idempotency import check_and_record_event, link_event_execution
from app.modules.executions.service import execute_workflow


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


DAY_NAME_TO_INT = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def compute_schedule_due_state(
    config: dict[str, Any],
    reference_time_utc: datetime,
) -> tuple[str, bool]:
    """
    Evaluates whether a workflow schedule is due at reference_time_utc in a
    connector-agnostic manner, respecting the configured timezone.
    
    Returns:
      (period_key, is_due)
    """
    tz_str = config.get("timezone", "UTC")
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("UTC")

    local_time = reference_time_utc.astimezone(tz)
    frequency = str(config.get("frequency", "daily")).lower()

    if frequency == "hourly":
        scheduled_minute = int(config.get("minute", 0))
        is_due = local_time.minute >= scheduled_minute
        # Period key isolates execution to this specific hour
        period_key = f"schedule:hourly:{local_time.strftime('%Y-%m-%d-%H')}"
        return period_key, is_due

    elif frequency == "daily":
        time_str = config.get("time", "00:00")
        try:
            h, m = map(int, time_str.split(":"))
        except Exception:
            h, m = 0, 0

        is_due = (local_time.hour > h) or (local_time.hour == h and local_time.minute >= m)
        # Period key isolates execution to this specific calendar day in the target timezone
        period_key = f"schedule:daily:{local_time.strftime('%Y-%m-%d')}"
        return period_key, is_due

    elif frequency == "weekly":
        raw_dow = config.get("day_of_week", "monday")
        if isinstance(raw_dow, int):
            target_dow = raw_dow
        else:
            target_dow = DAY_NAME_TO_INT.get(str(raw_dow).lower(), 0)

        time_str = config.get("time", "00:00")
        try:
            h, m = map(int, time_str.split(":"))
        except Exception:
            h, m = 0, 0

        current_dow = local_time.weekday()
        is_past_day = current_dow > target_dow
        is_same_day_time_passed = (current_dow == target_dow) and (
            (local_time.hour > h) or (local_time.hour == h and local_time.minute >= m)
        )
        is_due = is_past_day or is_same_day_time_passed

        # Period key isolates execution to this specific ISO calendar week in target timezone
        iso_year, iso_week, _ = local_time.isocalendar()
        period_key = f"schedule:weekly:{iso_year}-W{iso_week:02d}"
        return period_key, is_due

    return "schedule:unknown", False


def run_scheduled_workflow_cycle(
    db: Session,
    reference_time: datetime | None = None,
    organization_id: int | None = None,
) -> list[WorkflowExecution]:
    """
    Executes a scheduled workflow cycle (Module 6.4 & 6.5).
    Guarantees:
      1. Only 'published' workflows are evaluated (paused and drafts are rejected).
      2. Consumes immutable published version definition.
      3. Respects configured timezone (does not assume UTC or host timezone).
      4. Atomically enforces deduplication per schedule period key.
      5. Calls the existing execution engine execute_workflow() without a second engine.
      6. Enforces tenant isolation.
    """
    now = reference_time or _utc_now()

    # Query only active published workflows
    query = select(Workflow).where(Workflow.status == "published")
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflows = list(db.scalars(query).all())
    executed_list: list[WorkflowExecution] = []

    for wf in workflows:
        # Resolve published version
        published_version = db.scalar(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_id == wf.id,
                WorkflowVersion.published_at.is_not(None),
            )
            .order_by(WorkflowVersion.version_number.desc())
        )
        if not published_version:
            continue

        definition = published_version.definition or {}
        trigger = definition.get("trigger", {})

        is_schedule = (trigger.get("type") == "schedule") or (trigger.get("connector") == "schedule")
        if not is_schedule:
            continue

        config = trigger.get("config", {})
        period_key, is_due = compute_schedule_due_state(config, now)

        if not is_due:
            continue

        # Prevent duplicate execution for this schedule period
        is_new_period = check_and_record_event(
            db=db,
            workflow_id=wf.id,
            organization_id=wf.organization_id,
            event_key=period_key,
        )
        if not is_new_period:
            # Already executed for this hour/day/week period
            continue

        # Trigger execution using existing execution engine
        trigger_payload = {
            "schedule": config,
            "period_key": period_key,
            "triggered_at": now.isoformat(),
        }

        exec_record = execute_workflow(
            db=db,
            workflow_id=wf.id,
            trigger_data=trigger_payload,
            organization_id=wf.organization_id,
        )

        link_event_execution(
            db=db,
            workflow_id=wf.id,
            event_key=period_key,
            execution_id=exec_record.id,
        )

        # Update or create WorkflowTriggerState checkpoint
        trigger_state = db.scalar(
            select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == wf.id)
        )
        if not trigger_state:
            trigger_state = WorkflowTriggerState(
                workflow_id=wf.id,
                workflow_version_id=published_version.id,
                last_processed_event_key=period_key,
                last_polled_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(trigger_state)
        else:
            trigger_state.last_processed_event_key = period_key
            trigger_state.last_polled_at = now
            trigger_state.updated_at = now
        db.commit()

        executed_list.append(exec_record)

    return executed_list
