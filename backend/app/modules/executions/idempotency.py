import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import WorkflowTriggerEvent, WorkflowTriggerState


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def extract_event_key(record: dict[str, Any]) -> str:
    """
    Extracts a stable event key from a trigger payload in a connector-agnostic manner.
    
    Priority resolution:
      1. Explicit idempotency/event keys: 'idempotency_key', 'event_id', 'event_key', 'record_id', 'id'
      2. Common connector-agnostic record identifiers: 'row_index', 'lead_id', 'deal_id', 'contact_id'
      3. Fallback: SHA-256 hash of canonically sorted, deterministic JSON payload.
      
    LIMITATION NOTE (Module 6.3):
    Arbitrary payload hashing guarantees transport-level deduplication for identical
    event payloads (e.g. repeated trigger polling cycles or runner restarts). However,
    it cannot guarantee business-level semantic idempotency if the provider alters
    ephemeral payload fields (e.g., timestamps, nonces, or dynamic tokens) for the
    same underlying business entity. Whenever possible, connector triggers should
    include a stable entity or event ID.
    """
    if not isinstance(record, dict):
        return hashlib.sha256(str(record).encode("utf-8")).hexdigest()

    # 1. Direct explicit event / idempotency identifiers
    explicit_keys = ("idempotency_key", "event_id", "event_key", "record_id", "id")
    for k in explicit_keys:
        val = record.get(k)
        if val is not None and str(val).strip():
            return f"{k}:{str(val).strip()}"

    # 2. Common domain identifiers
    domain_keys = ("row_index", "lead_id", "deal_id", "contact_id", "ticket_id", "order_id")
    for k in domain_keys:
        val = record.get(k)
        if val is not None and str(val).strip():
            return f"{k}:{str(val).strip()}"

    # 3. Check values dictionary if present (e.g., row values)
    if "values" in record and isinstance(record["values"], dict):
        vals = record["values"]
        for k in ("Email", "email", "id", "ID", "lead_id", "row_id"):
            val = vals.get(k)
            if val is not None and str(val).strip():
                return f"values.{k}:{str(val).strip()}"

    # 4. Canonical payload hashing fallback
    try:
        serialized = json.dumps(record, sort_keys=True, default=str)
    except Exception:
        serialized = str(sorted(record.items()))

    payload_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"hash:{payload_hash}"


def check_and_record_event(
    db: Session,
    workflow_id: int,
    organization_id: int,
    event_key: str,
    execution_id: int | None = None,
) -> bool:
    """
    Checks if an event key has already been processed for this workflow.
    If new, atomically records it into WorkflowTriggerEvent.
    
    Returns:
      True: if the event is new (recorded successfully, workflow can proceed)
      False: if the event has already been processed (duplicate, must skip)
    """
    # 1. Fast existence check
    existing = db.scalar(
        select(WorkflowTriggerEvent.id).where(
            WorkflowTriggerEvent.workflow_id == workflow_id,
            WorkflowTriggerEvent.event_key == event_key,
        )
    )
    if existing:
        return False

    # 2. Atomic insert with race condition protection
    now = _utc_now()
    event_record = WorkflowTriggerEvent(
        workflow_id=workflow_id,
        organization_id=organization_id,
        event_key=event_key,
        execution_id=execution_id,
        created_at=now,
    )
    db.add(event_record)
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def link_event_execution(
    db: Session,
    workflow_id: int,
    event_key: str,
    execution_id: int,
) -> None:
    """
    Links the created execution ID to the recorded trigger event and updates
    WorkflowTriggerState.last_processed_event_key.
    """
    event_record = db.scalar(
        select(WorkflowTriggerEvent).where(
            WorkflowTriggerEvent.workflow_id == workflow_id,
            WorkflowTriggerEvent.event_key == event_key,
        )
    )
    if event_record:
        event_record.execution_id = execution_id

    # Also update state last_processed_event_key if trigger state exists
    state = db.scalar(
        select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == workflow_id)
    )
    if state:
        state.last_processed_event_key = event_key

    db.commit()
