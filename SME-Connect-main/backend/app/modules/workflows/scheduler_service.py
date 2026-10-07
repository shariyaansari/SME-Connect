from datetime import datetime, timezone
import logging
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Workflow, WorkflowExecution, WorkflowVersion
from app.modules.workflows.execution_service import execute_workflow
from app.modules.workflows.idempotency import is_event_duplicate, record_idempotency

logger = logging.getLogger(__name__)

DAY_OF_WEEK_MAP: dict[str, int] = {
    "mon": 0, "monday": 0, "0": 0,
    "tue": 1, "tuesday": 1, "1": 1,
    "wed": 2, "wednesday": 2, "2": 2,
    "thu": 3, "thursday": 3, "3": 3,
    "fri": 4, "friday": 4, "4": 4,
    "sat": 5, "saturday": 5, "5": 5,
    "sun": 6, "sunday": 6, "6": 6,
}


def validate_timezone(tz_str: str | None) -> ZoneInfo:
    """Validates and returns a ZoneInfo instance, falling back to UTC if None/empty."""
    if not tz_str:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(tz_str.strip())
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ValueError(f"Invalid timezone: '{tz_str}'")


def is_schedule_due(trigger_config: dict[str, Any], current_time: datetime) -> tuple[bool, str]:
    """
    Evaluates whether a scheduled workflow trigger is due at `current_time`.
    Supports 'hourly', 'daily', and 'weekly' recurrence frequencies.
    Returns: (is_due, slot_identifier)
    """
    tz = validate_timezone(trigger_config.get("timezone", "UTC"))
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    local_time = current_time.astimezone(tz)

    frequency = str(trigger_config.get("frequency", "hourly")).lower().strip()
    target_minute = int(trigger_config.get("minute", 0))

    if frequency == "hourly":
        slot_id = f"hourly:{local_time.strftime('%Y-%m-%d-%H')}"
        is_due = local_time.minute >= target_minute
        return is_due, slot_id

    elif frequency == "daily":
        target_hour = int(trigger_config.get("hour", 0))
        slot_id = f"daily:{local_time.strftime('%Y-%m-%d')}"
        is_due = (local_time.hour > target_hour) or (
            local_time.hour == target_hour and local_time.minute >= target_minute
        )
        return is_due, slot_id

    elif frequency == "weekly":
        target_hour = int(trigger_config.get("hour", 0))
        raw_dow = str(trigger_config.get("day_of_week", "0")).lower().strip()
        target_dow = DAY_OF_WEEK_MAP.get(raw_dow, 0)
        iso_year, iso_week, _ = local_time.isocalendar()
        slot_id = f"weekly:{iso_year}-W{iso_week:02d}-{target_dow}"
        
        matches_day = local_time.weekday() == target_dow
        matches_time = (local_time.hour > target_hour) or (
            local_time.hour == target_hour and local_time.minute >= target_minute
        )
        is_due = matches_day and matches_time
        return is_due, slot_id

    else:
        # Unknown frequency
        return False, f"unknown:{frequency}"


def run_scheduled_workflow_cycle(
    db: Session,
    current_time: datetime | None = None,
    organization_id: int | None = None,
) -> list[WorkflowExecution]:
    """
    Evaluates all published workflows configured with a 'schedule' connector trigger.
    Enforces slot-based idempotency to avoid duplicate executions within the recurrence window.
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    # 1. Query published workflows
    query = select(Workflow).where(Workflow.status == "published")
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflows = list(db.scalars(query).all())
    executed: list[WorkflowExecution] = []

    for wf in workflows:
        # 2. Get active published version
        version = db.scalar(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_id == wf.id,
                WorkflowVersion.published_at.is_not(None),
            )
            .order_by(WorkflowVersion.version_number.desc())
        )
        if not version or not isinstance(version.definition, dict):
            continue

        trigger_data = version.definition.get("trigger", {})
        if trigger_data.get("connector") != "schedule":
            continue

        trigger_config = trigger_data.get("config", {})

        try:
            is_due, slot_id = is_schedule_due(trigger_config, current_time)
        except Exception as exc:
            logger.warning(f"Error evaluating schedule trigger for workflow {wf.id}: {exc}")
            continue

        if not is_due:
            continue

        # 3. Check deduplication key
        idempotency_key = f"sched:{wf.id}:{slot_id}"
        if is_event_duplicate(db, wf.id, idempotency_key):
            logger.info(f"Skipping scheduled workflow {wf.id}; already executed for slot {slot_id}")
            continue

        # 4. Trigger execution safely
        tz_obj = validate_timezone(trigger_config.get("timezone", "UTC"))
        payload = {
            "scheduled_time": current_time.isoformat(),
            "frequency": trigger_config.get("frequency", "hourly"),
            "timezone": str(tz_obj),
            "slot": slot_id,
        }

        try:
            exec_record = execute_workflow(
                db=db,
                workflow_id=wf.id,
                trigger_data=payload,
                organization_id=wf.organization_id,
            )
            record_idempotency(
                db=db,
                workflow_id=wf.id,
                organization_id=wf.organization_id,
                idempotency_key=idempotency_key,
                execution_id=exec_record.id,
                event_payload=payload,
            )
            executed.append(exec_record)
        except Exception as exc:
            logger.error(f"Failed to execute scheduled workflow {wf.id}: {exc}")

    return executed
