from datetime import datetime, timezone
from typing import Any
import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decrypt_credentials
from app.database.models import Connection, Workflow, WorkflowTriggerState, WorkflowVersion
from app.modules.connectors.registry import get_adapter
from app.modules.workflows.execution_service import execute_workflow
from app.modules.workflows.idempotency import generate_idempotency_key, is_event_duplicate, record_idempotency
from app.modules.workflows.schemas import WorkflowDefinition

logger = logging.getLogger(__name__)


def get_or_create_trigger_state(
    db: Session,
    workflow: Workflow,
    version_id: int,
) -> WorkflowTriggerState:
    """
    Retrieves or creates persistent trigger cursor checkpoint storage for a workflow.
    Guarantees strict tenant and workflow isolation.
    """
    trigger_state = db.scalar(
        select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == workflow.id)
    )

    if not trigger_state:
        trigger_state = WorkflowTriggerState(
            workflow_id=workflow.id,
            workflow_version_id=version_id,
            organization_id=workflow.organization_id,
            cursor=None,
            last_polled_at=None,
        )
        db.add(trigger_state)
        db.flush()

    return trigger_state


def poll_workflow_trigger(
    db: Session,
    workflow: Workflow,
) -> dict[str, Any]:
    """
    Polls events for a single published workflow and runs executions for returned records.
    
    Invariants:
      1. Only 'published' workflows are polled (draft and paused are rejected).
      2. Completely connector-agnostic: resolves adapter dynamically via ConnectorRegistry.
      3. Advances cursor only after successful execution handling.
      4. Decrypts credentials strictly in memory.
    """
    if workflow.status != "published":
        return {
            "workflow_id": workflow.id,
            "status": "skipped",
            "reason": f"Workflow is not published (status: '{workflow.status}')",
        }

    # Resolve active published WorkflowVersion
    version = db.scalar(
        select(WorkflowVersion)
        .where(
            WorkflowVersion.workflow_id == workflow.id,
            WorkflowVersion.published_at.is_not(None),
        )
        .order_by(WorkflowVersion.version_number.desc())
    )
    if not version:
        return {
            "workflow_id": workflow.id,
            "status": "skipped",
            "reason": "No published version found",
        }

    definition = WorkflowDefinition.model_validate(version.definition)
    trigger = definition.trigger

    # Resolve connector adapter generically
    adapter = get_adapter(trigger.connector)
    if not adapter:
        return {
            "workflow_id": workflow.id,
            "status": "error",
            "reason": f"Connector '{trigger.connector}' not found in registry",
        }

    # Resolve active organization connection
    connection = db.scalar(
        select(Connection).where(
            Connection.organization_id == workflow.organization_id,
            Connection.connector_slug == trigger.connector,
            Connection.status == "active",
        )
    )
    if not connection:
        return {
            "workflow_id": workflow.id,
            "status": "skipped",
            "reason": f"No active connection found for connector '{trigger.connector}'",
        }

    # Decrypt credentials in memory only
    credentials = decrypt_credentials(connection.credentials)
    merged_config = {**connection.config, **trigger.config}

    # Retrieve or create cursor checkpoint state
    trigger_state = get_or_create_trigger_state(db, workflow, version.id)

    # Invoke connector adapter to read trigger events
    try:
        records, new_cursor = adapter.read_trigger_data(
            trigger_slug=trigger.event,
            config=merged_config,
            credentials=credentials,
            cursor=trigger_state.cursor,
        )
    except Exception as exc:
        logger.error(f"Trigger polling failed for workflow {workflow.id}: {exc}")
        return {
            "workflow_id": workflow.id,
            "status": "error",
            "reason": f"Connector adapter trigger read failed: {str(exc)}",
        }

    execution_ids: list[int] = []
    executions_succeeded = True
    skipped_duplicates = 0

    # Process returned events sequentially through execution engine with idempotency protection
    for record in records:
        idempotency_key = generate_idempotency_key(record)
        if is_event_duplicate(db, workflow.id, idempotency_key):
            skipped_duplicates += 1
            logger.info(
                f"Skipping duplicate event for workflow {workflow.id} with idempotency key {idempotency_key}"
            )
            continue

        try:
            execution = execute_workflow(
                db=db,
                workflow_id=workflow.id,
                trigger_data=record,
                organization_id=workflow.organization_id,
            )
            record_idempotency(
                db=db,
                workflow_id=workflow.id,
                organization_id=workflow.organization_id,
                idempotency_key=idempotency_key,
                execution_id=execution.id,
            )
            execution_ids.append(execution.id)
            if execution.status == "failed":
                executions_succeeded = False
        except Exception as exc:
            logger.error(f"Workflow execution failed during trigger handling: {exc}")
            executions_succeeded = False

    # Advance cursor checkpoint only after processing
    now = datetime.now(timezone.utc)
    trigger_state.last_polled_at = now
    trigger_state.workflow_version_id = version.id

    if records and executions_succeeded:
        trigger_state.cursor = new_cursor

    db.commit()
    db.refresh(trigger_state)

    return {
        "workflow_id": workflow.id,
        "status": "success",
        "records_count": len(records),
        "execution_ids": execution_ids,
        "skipped_duplicates": skipped_duplicates,
        "new_cursor": trigger_state.cursor,
    }


def run_trigger_poll_cycle(
    db: Session,
    organization_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Runs a periodic trigger polling cycle across all active published workflows.
    Enforces multi-tenant isolation and graceful per-workflow error isolation.
    """
    query = (
        select(Workflow)
        .where(Workflow.status == "published")
        .order_by(Workflow.id.asc())
    )
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflows = db.scalars(query).all()
    results: list[dict[str, Any]] = []

    for wf in workflows:
        try:
            wf_result = poll_workflow_trigger(db, wf)
            results.append(wf_result)
        except Exception as exc:
            logger.error(f"Unexpected error polling workflow {wf.id}: {exc}")
            results.append({
                "workflow_id": wf.id,
                "status": "error",
                "reason": str(exc),
            })

    return results
