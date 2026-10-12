import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import WorkflowTriggerEvent, WorkflowTriggerState

logger = logging.getLogger(__name__)


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


# ============================================================================
# Distributed Redis / In-Memory Lock Backend (SETNX Semantics)
# ============================================================================

class RedisIdempotencyBackend:
    """
    Redis-compatible idempotency engine supporting strict SETNX semantics.
    Falls back gracefully when Redis is not configured or offline.
    """

    def __init__(self, redis_client: Any = None):
        self._client = redis_client

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            try:
                import redis
                self._client = redis.Redis.from_url(redis_url)
                return self._client
            except Exception as e:
                logger.warning(f"Could not initialize Redis client from REDIS_URL: {e}")
        return None

    def acquire(self, lock_key: str, ttl_seconds: int = 3600) -> bool:
        client = self._get_client()
        if client is None:
            return True  # Proceed to DB-backed atomic lock
        try:
            # SET lock_key "1" NX EX ttl_seconds -> returns True only if newly set
            acquired = client.set(f"sme_connect:idem:{lock_key}", "locked", nx=True, ex=ttl_seconds)
            return bool(acquired)
        except Exception as e:
            logger.warning(f"Redis SETNX lock check failed; falling back to DB lock: {e}")
            return True

    def release(self, lock_key: str) -> None:
        client = self._get_client()
        if client is not None:
            try:
                client.delete(f"sme_connect:idem:{lock_key}")
            except Exception:
                pass


# Global pluggable Redis backend instance
_redis_backend = RedisIdempotencyBackend()


def set_custom_idempotency_backend(backend: RedisIdempotencyBackend | None) -> None:
    """Allows injecting custom or mock Redis backend for testing."""
    global _redis_backend
    _redis_backend = backend or RedisIdempotencyBackend()


# ============================================================================
# Atomic Database-Backed Acquisition Engine (SELECT FOR UPDATE / SAVEPOINT)
# ============================================================================

def check_and_record_event(
    db: Session,
    workflow_id: int,
    organization_id: int,
    event_key: str,
    execution_id: int | None = None,
    ttl_seconds: int = 3600,
) -> bool:
    """
    Strict atomic acquisition of an event idempotency token.
    
    Guarantees:
      1. Evaluates Redis SETNX lock if Redis is configured.
      2. Fast existence check with SELECT FOR UPDATE (where supported) to prevent concurrent races.
      3. Atomic insert inside a nested transaction (SAVEPOINT). If a concurrent worker races
         and commits the identical (workflow_id, event_key), IntegrityError rolls back ONLY
         the savepoint, leaving the outer database session clean and uncorrupted.
      4. Never exposes or relies on volatile in-memory process dictionaries.
      
    Returns:
      True: if the event token was atomically acquired (new event, workflow execution can proceed)
      False: if the event has already been recorded or locked by a concurrent worker (duplicate, skip)
    """
    lock_key = f"{organization_id}:{workflow_id}:{event_key}"

    # 1. First line of defense: Redis SETNX atomic check (if active)
    if _redis_backend and not _redis_backend.acquire(lock_key, ttl_seconds=ttl_seconds):
        return False

    # 2. Fast existence check with row-level locking if supported by dialect
    query = select(WorkflowTriggerEvent.id).where(
        WorkflowTriggerEvent.workflow_id == workflow_id,
        WorkflowTriggerEvent.event_key == event_key,
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        query = query.with_for_update()

    existing = db.scalar(query)
    if existing:
        return False

    # 3. Atomic insertion using nested transaction (SAVEPOINT)
    now = _utc_now()
    event_record = WorkflowTriggerEvent(
        workflow_id=workflow_id,
        organization_id=organization_id,
        event_key=event_key,
        execution_id=execution_id,
        created_at=now,
    )

    try:
        with db.begin_nested():
            db.add(event_record)
            db.flush()
        db.commit()
        return True
    except Exception:
        # Savepoint rolled back automatically. The outer session is completely unpoisoned.
        if _redis_backend:
            _redis_backend.release(lock_key)
        return False


def link_event_execution(
    db: Session,
    workflow_id: int,
    event_key: str,
    execution_id: int,
) -> None:
    """
    Atomically links the created execution ID to the recorded trigger event and updates
    WorkflowTriggerState.last_processed_event_key with row-level locking where supported.
    """
    event_query = select(WorkflowTriggerEvent).where(
        WorkflowTriggerEvent.workflow_id == workflow_id,
        WorkflowTriggerEvent.event_key == event_key,
    )
    if db.bind and db.bind.dialect.name == "postgresql":
        event_query = event_query.with_for_update()

    event_record = db.scalar(event_query)
    if event_record:
        event_record.execution_id = execution_id

    # Update state last_processed_event_key with row-level locking
    state_query = select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == workflow_id)
    if db.bind and db.bind.dialect.name == "postgresql":
        state_query = state_query.with_for_update()

    state = db.scalar(state_query)
    if state:
        state.last_processed_event_key = event_key

    db.commit()
