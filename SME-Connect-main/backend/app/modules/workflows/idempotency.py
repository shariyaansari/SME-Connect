import hashlib
import json
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import WorkflowExecutionDeduplication


def generate_idempotency_key(trigger_event: dict[str, Any]) -> str:
    """
    Generates a connector-agnostic idempotency key for a trigger event.
    
    1. If the adapter or payload supplies a stable event identifier
       (e.g., 'event_id', 'idempotency_key', 'row_id', 'message_id', 'id'),
       that stable key is used.
    2. Otherwise, calculates a deterministic SHA-256 hash of the canonical serialized payload.
    
    Limitation Note:
    Payload hashing handles accidental duplicate polls of identical data, but business-level
    idempotency is most robust when adapters or webhook events provide a stable event ID.
    """
    if not isinstance(trigger_event, dict):
        serialized = json.dumps(trigger_event, sort_keys=True, default=str)
        return f"hash:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"

    # Check top-level candidate keys
    candidate_keys = ("idempotency_key", "event_id", "row_id", "message_id", "charge_id", "lead_id", "id")
    for key in candidate_keys:
        val = trigger_event.get(key)
        if val is not None and str(val).strip():
            return f"evt:{str(val).strip()}"

    # Check nested values dictionary
    values = trigger_event.get("values")
    if isinstance(values, dict):
        for key in candidate_keys:
            val = values.get(key)
            if val is not None and str(val).strip():
                return f"evt:{str(val).strip()}"

    # Fallback: Canonical content hash
    serialized = json.dumps(trigger_event, sort_keys=True, default=str)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"hash:{digest}"


def is_event_duplicate(
    db: Session,
    workflow_id: int,
    idempotency_key: str,
) -> bool:
    """
    Checks whether the event has already produced an execution for this workflow.
    """
    existing = db.scalar(
        select(WorkflowExecutionDeduplication).where(
            WorkflowExecutionDeduplication.workflow_id == workflow_id,
            WorkflowExecutionDeduplication.idempotency_key == idempotency_key,
        )
    )
    return existing is not None


def record_idempotency(
    db: Session,
    workflow_id: int,
    organization_id: int,
    idempotency_key: str,
    execution_id: int,
    event_payload: Any | None = None,
) -> WorkflowExecutionDeduplication:
    """
    Records an execution idempotency key for duplicate prevention.
    """
    dedup = WorkflowExecutionDeduplication(
        workflow_id=workflow_id,
        organization_id=organization_id,
        idempotency_key=idempotency_key,
        execution_id=execution_id,
    )
    db.add(dedup)
    db.flush()
    return dedup
