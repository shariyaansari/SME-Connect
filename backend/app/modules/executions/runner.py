from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decrypt_credentials
from app.database.models import Connection, Workflow, WorkflowExecution, WorkflowTriggerState, WorkflowVersion
from app.modules.connectors.registry import get_adapter
from app.modules.executions.idempotency import (
    check_and_record_event,
    extract_event_key,
    link_event_execution,
)
from app.modules.executions.resolver import sanitize_error_message
from app.modules.executions.service import execute_workflow


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def poll_workflow_trigger(
    db: Session,
    workflow_id: int,
    organization_id: int | None = None,
) -> list[WorkflowExecution]:
    """
    Polls trigger events for a published workflow and executes it in a connector-agnostic manner.
    Guarantees:
      1. Enforces workflow status == 'published'.
      2. Consumes immutable published version definition.
      3. Retrieves organization-scoped cursor checkpoint from WorkflowTriggerState.
      4. Invokes adapter.read_trigger_data() without connector-specific branching.
      5. Advances the cursor if and only after records are successfully handled.
    """
    query = select(Workflow).where(Workflow.id == workflow_id)
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflow = db.scalar(query)
    if not workflow:
        raise ValueError("Workflow not found")

    if workflow.status != "published":
        raise ValueError(
            f"Cannot poll workflow with status '{workflow.status}'. Workflow must be 'published'."
        )

    # 1. Resolve published version
    published_version = db.scalar(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == workflow.id,
            WorkflowVersion.published_at.is_not(None),
        )
        .order_by(WorkflowVersion.version_number.desc())
    )
    if not published_version:
        raise ValueError("No published version found for this workflow")

    definition = published_version.definition or {}
    trigger_def = definition.get("trigger", {})
    connector_slug = trigger_def.get("connector", "")
    trigger_slug = trigger_def.get("event", "")
    trigger_config = trigger_def.get("config", {})

    # 2. Resolve adapter generically via registry
    adapter = get_adapter(connector_slug)
    if not adapter:
        raise ValueError(f"Unknown trigger connector '{connector_slug}'")

    # 3. Resolve active organization connection
    connection = db.scalar(
        select(Connection).where(
            Connection.organization_id == workflow.organization_id,
            Connection.connector_slug == connector_slug,
            Connection.status == "active",
        )
    )
    if not connection:
        raise ValueError(
            f"No active connection found for trigger connector '{connector_slug}' in this organization"
        )

    # 4. Resolve persistent cursor state
    trigger_state = db.scalar(
        select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == workflow.id)
    )
    current_cursor = trigger_state.cursor if trigger_state else None

    # 5. Decrypt credentials in-memory only
    creds = decrypt_credentials(connection.credentials)
    runtime_config = dict(connection.config or {})
    runtime_config.update(trigger_config)

    # 6. Read trigger data via adapter contract
    try:
        records, new_cursor = adapter.read_trigger_data(
            trigger_slug=trigger_slug,
            config=runtime_config,
            credentials=creds,
            cursor=current_cursor,
        )
    finally:
        del creds  # Sensitive credentials promptly removed from scope

    now = _utc_now()
    if not records:
        # Update last_polled_at without altering cursor
        if not trigger_state:
            trigger_state = WorkflowTriggerState(
                workflow_id=workflow.id,
                workflow_version_id=published_version.id,
                cursor=current_cursor,
                last_polled_at=now,
                created_at=now,
                updated_at=now,
            )
            db.add(trigger_state)
        else:
            trigger_state.last_polled_at = now
            trigger_state.updated_at = now
        db.commit()
        return []

    # 7. Process returned records & create executions with idempotency protection
    executions: list[WorkflowExecution] = []
    last_processed_key = None
    for record in records:
        event_key = extract_event_key(record)
        is_new_event = check_and_record_event(
            db=db,
            workflow_id=workflow.id,
            organization_id=workflow.organization_id,
            event_key=event_key,
        )
        if not is_new_event:
            # Duplicate trigger event detected; skip execution to prevent double processing
            continue

        exec_record = execute_workflow(
            db=db,
            workflow_id=workflow.id,
            trigger_data=record,
            organization_id=workflow.organization_id,
        )
        link_event_execution(
            db=db,
            workflow_id=workflow.id,
            event_key=event_key,
            execution_id=exec_record.id,
        )
        last_processed_key = event_key
        executions.append(exec_record)

    # 8. Advance cursor only after handling records
    if not trigger_state:
        trigger_state = WorkflowTriggerState(
            workflow_id=workflow.id,
            workflow_version_id=published_version.id,
            cursor=new_cursor,
            last_processed_event_key=last_processed_key,
            last_polled_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(trigger_state)
    else:
        trigger_state.cursor = new_cursor
        trigger_state.workflow_version_id = published_version.id
        if last_processed_key:
            trigger_state.last_processed_event_key = last_processed_key
        trigger_state.last_polled_at = now
        trigger_state.updated_at = now

    db.commit()
    db.refresh(trigger_state)
    return executions


def run_trigger_poll_cycle(
    db: Session,
    organization_id: int | None = None,
) -> dict[str, Any]:
    """
    Executes a periodic polling cycle across all published workflows.
    Ensures cursor advancement happens only upon successful processing.
    """
    query = select(Workflow).where(Workflow.status == "published")
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflows = list(db.scalars(query).all())

    polled_count = 0
    events_count = 0
    executions_count = 0
    errors: list[str] = []

    for wf in workflows:
        try:
            results = poll_workflow_trigger(
                db=db,
                workflow_id=wf.id,
                organization_id=wf.organization_id,
            )
            polled_count += 1
            events_count += len(results)
            executions_count += len(results)
        except Exception as exc:
            clean_err = sanitize_error_message(str(exc))
            errors.append(f"Workflow {wf.id} poll error: {clean_err}")

    return {
        "workflows_polled": polled_count,
        "events_detected": events_count,
        "executions_created": executions_count,
        "errors": errors,
    }
