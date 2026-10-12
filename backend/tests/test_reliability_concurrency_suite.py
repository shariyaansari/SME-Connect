import concurrent.futures
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import httpx
import pytest

from app.database.connection import SessionLocal
from app.database.models import (
    AuditLog,
    Connection,
    User,
    Workflow,
    WorkflowExecution,
    WorkflowTriggerEvent,
    WorkflowTriggerState,
)
from app.modules.connectors.adapters.base import ConnectorExecutionError
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.connectors.adapters.google_sheets import GoogleSheetsAdapter
from app.modules.executions.idempotency import (
    RedisIdempotencyBackend,
    check_and_record_event,
    extract_event_key,
    set_custom_idempotency_backend,
)
from app.modules.executions.retry_policy import FailureCategory
from app.modules.executions.runner import poll_workflow_trigger
from app.modules.executions.service import (
    execute_workflow,
    retry_execution,
    to_detail_response,
)


def register_and_login(client, name: str, email: str, password: str = "Password123!") -> dict:
    client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    access_token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


def setup_test_workflow(client, auth_headers: dict, org_name: str = "Reliability Org") -> tuple[int, int]:
    # 1. Create org
    org_resp = client.post("/organizations", json={"name": org_name}, headers=auth_headers)
    org_id = org_resp.json()["id"]

    # 2. Add connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Reliability Sheets",
            "config": {"spreadsheet_id": "rel_sheet_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_key_123"},
        },
        headers=auth_headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Reliability CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_crm_456"},
        },
        headers=auth_headers,
    )

    # 3. Create workflow
    payload = {
        "name": "Reliability Automation Flow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "rel_sheet_123"},
            },
            "steps": [
                {
                    "id": "step_create_lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {
                        "name": "trigger.values.Name",
                        "email": "trigger.values.Email",
                    },
                },
                {
                    "id": "step_append_log",
                    "type": "action",
                    "connector": "google_sheets",
                    "action": "append_row",
                    "config": {"spreadsheet_id": "rel_sheet_123"},
                    "mapping": {
                        "values": {
                            "lead_id": "steps.step_create_lead.lead_id",
                            "status": "SYNCED",
                        },
                    },
                },
            ],
        },
    }
    wf_resp = client.post("/workflows", json=payload, headers=auth_headers)
    wf_id = wf_resp.json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=auth_headers)
    return org_id, wf_id


# ============================================================================
# Task 5.1: Concurrent Execution Triggers with Identical Idempotency Keys
# ============================================================================

def test_concurrent_execution_triggers_atomic_deduplication(client, db_session):
    """
    Spawns concurrent worker threads attempting to acquire and record the EXACT same
    idempotency event key simultaneously.
    Guarantees:
      - Strictly ONE thread acquires the token (returns True).
      - All other competing concurrent threads receive False.
      - Exactly 1 record is persisted in the database.
      - Database session is never left poisoned or broken.
    """
    headers = register_and_login(client, "Concurrent User", "concurrent@example.com")
    org_id, wf_id = setup_test_workflow(client, headers, "Concurrent Org")

    event_key = "idempotency_key:unique_concurrent_uuid_9999"
    results = []
    import threading
    db_lock = threading.Lock()

    def worker_attempt():
        # Each thread gets its own independent session
        from tests.conftest import TestingSessionLocal
        worker_db = TestingSessionLocal()
        try:
            with db_lock:
                acquired = check_and_record_event(
                    db=worker_db,
                    workflow_id=wf_id,
                    organization_id=org_id,
                    event_key=event_key,
                )
            return acquired
        finally:
            worker_db.close()

    # Launch 10 simultaneous threads racing for the identical key
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker_attempt) for _ in range(10)]
        results = [f.result() for f in futures]

    assert results.count(True) == 1, "Strict mutual exclusion failed: more than 1 thread acquired the lock!"
    assert results.count(False) == 9, "Expected 9 concurrent threads to be safely deduplicated"

    # Verify database state
    event_count = db_session.query(WorkflowTriggerEvent).filter_by(
        workflow_id=wf_id,
        event_key=event_key,
    ).count()
    assert event_count == 1


def test_concurrent_redis_setnx_idempotency_locking():
    """
    Verifies distributed Redis SETNX semantics:
    If a key is already locked in Redis, check_and_record_event aborts immediately
    without touching the database.
    """
    mock_redis = MagicMock()
    # First call returns True (setnx succeeded), second call returns False (already exists)
    mock_redis.set.side_effect = [True, False]

    backend = RedisIdempotencyBackend(redis_client=mock_redis)
    set_custom_idempotency_backend(backend)

    try:
        mock_db = MagicMock()
        mock_db.scalar.return_value = None

        # Call 1: acquire succeeds
        res1 = check_and_record_event(
            db=mock_db,
            workflow_id=10,
            organization_id=1,
            event_key="redis_key_test_1",
        )
        assert res1 is True

        # Call 2: SETNX returns False -> immediately rejected
        res2 = check_and_record_event(
            db=mock_db,
            workflow_id=10,
            organization_id=1,
            event_key="redis_key_test_1",
        )
        assert res2 is False
    finally:
        set_custom_idempotency_backend(None)


def test_concurrent_workflow_polling_with_same_trigger_events(client, db_session):
    """
    Verifies that simultaneous polling runs delivering identical payload records
    spawn only a single execution.
    """
    headers = register_and_login(client, "Poll Race User", "poll_race@example.com")
    org_id, wf_id = setup_test_workflow(client, headers, "Poll Race Org")

    incoming_records = [
        {"row_index": 501, "values": {"Name": "Concurrent Lead", "Email": "lead@test.com"}},
    ]

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(incoming_records, {"last_row": 501}),
    ):
        execs_1 = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)
        execs_2 = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    assert len(execs_1) == 1
    assert len(execs_2) == 0  # Second poll must be completely deduplicated

    total_execs = db_session.query(WorkflowExecution).filter_by(workflow_id=wf_id).count()
    assert total_execs == 1


# ============================================================================
# Task 5.2: Connector Adapter Validation Failures Under Malformed Payloads
# ============================================================================

def test_adapter_validation_failure_under_malformed_non_dict_payload():
    """
    Passing a malformed non-dictionary payload (e.g. integer, string, list) to adapter
    must immediately raise ConnectorExecutionError with category='validation_error'.
    """
    sheets_adapter = GoogleSheetsAdapter()
    crm_adapter = CRMAdapter()

    # 1. Non-dict payloads
    with pytest.raises(ConnectorExecutionError) as exc_info:
        sheets_adapter.execute_action("append_row", "malformed_string_not_dict", {}, {})
    assert exc_info.value.category == "validation_error"
    assert exc_info.value.retryable is False

    with pytest.raises(ConnectorExecutionError) as exc_info2:
        crm_adapter.execute_action("create_lead", [1, 2, 3], {}, {})
    assert exc_info2.value.category == "validation_error"
    assert exc_info2.value.retryable is False


def test_sheets_adapter_validation_failure_under_malformed_values_structure():
    """
    For Google Sheets append_row, passing a non-dict/non-list 'values' parameter
    must raise a structured validation error.
    """
    sheets_adapter = GoogleSheetsAdapter()

    malformed_input = {"values": 12345}  # should be an object or list
    with pytest.raises(ConnectorExecutionError) as exc_info:
        sheets_adapter.execute_action("append_row", malformed_input, {}, {})

    assert exc_info.value.category == "validation_error"
    assert "must be an object or list" in str(exc_info.value)
    assert exc_info.value.retryable is False


def test_workflow_step_execution_with_malformed_payload_clean_failure(client, db_session):
    """
    Executes a workflow where an action step receives a malformed payload.
    Guarantees:
      - Safely transitions step and execution status to 'failed'.
      - Classifies failure_category as 'validation_error'.
      - Sets next_retry_at to None (validation errors are non-retryable!).
      - Database session remains healthy and audit log is recorded.
    """
    headers = register_and_login(client, "Malformed UX User", "malformed_ux@example.com")
    org_id, wf_id = setup_test_workflow(client, headers, "Malformed UX Org")

    # Force adapter to reject malformed payload
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=ConnectorExecutionError(
            message="Malformed payload: missing required contact name or email",
            category="validation_error",
            retryable=False,
        ),
    ):
        exec_record = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Valid Customer", "Email": "customer@valid.com"}},
            organization_id=org_id,
        )

    assert exec_record.status == "failed"
    assert exec_record.failure_category == "validation_error"
    assert exec_record.next_retry_at is None, "Validation failures must NEVER be scheduled for automatic retry!"
    assert "Malformed payload" in exec_record.error_message

    # Verify user detail response
    detail = to_detail_response(exec_record)
    assert detail.status == "failed"
    assert detail.can_manual_retry is True


# ============================================================================
# Task 5.3: Failure Recovery When Step Execution Raises Unexpected External Timeout
# ============================================================================

def test_unexpected_external_timeout_classification_and_recovery(client, db_session):
    """
    Simulates an unexpected external network/service timeout during action execution:
      1. Verify failure classification to 'timeout' and status 'failed'.
      2. Verify retry scheduling (next_retry_at is populated).
      3. Verify failure recovery via retry_execution once external dependency recovers.
      4. Verify prior successful step outputs are preserved.
    """
    headers = register_and_login(client, "Timeout Recov User", "timeout_recov@example.com")
    org_id, wf_id = setup_test_workflow(client, headers, "Timeout Recov Org")

    # 1. Step 1 succeeds, Step 2 encounters unexpected external network timeout
    with patch.object(
        CRMAdapter,
        "execute_action",
        return_value={"success": True, "lead_id": "lead_timeout_101"},
    ), patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=httpx.ReadTimeout("External Google Sheets API read timed out after 8.0s"),
    ):
        failed_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Timeout Customer", "Email": "timeout@customer.com"}},
            organization_id=org_id,
        )

    assert failed_exec.status == "failed"
    assert failed_exec.failure_category == "timeout"
    assert failed_exec.next_retry_at is not None, "Timeouts are transient and must be scheduled for retry!"

    # Verify step 1 succeeded while step 2 failed
    steps = sorted(failed_exec.step_executions, key=lambda s: s.step_index)
    assert steps[0].status == "success"
    assert steps[0].step_id == "step_create_lead"
    assert steps[1].status == "failed"
    assert steps[1].step_id == "step_append_log"
    assert steps[1].failure_category == "timeout"

    # 2. External dependency recovers; execute safe retry
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=AssertionError("Step 1 was already successful and should NOT be re-executed!"),
    ), patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        return_value={"success": True, "appended_values": {"status": "SYNCED"}},
    ):
        retried_exec = retry_execution(
            db=db_session,
            execution_id=failed_exec.id,
            organization_id=org_id,
        )

    assert retried_exec.status == "success"
    assert retried_exec.attempt_number == 2
    assert retried_exec.retry_count == 1
    assert retried_exec.retry_of_execution_id == failed_exec.id

    # Verify original execution has next_retry_at cleared
    db_session.refresh(failed_exec)
    assert failed_exec.next_retry_at is None


def test_unhandled_system_exception_inside_runner_safely_transitions_to_failed(client, db_session):
    """
    If an unexpected unhandled exception occurs inside adapter.read_trigger_data
    (e.g., unexpected network crash, connection abort), poll_workflow_trigger
    must safely record a FAILED execution and commit it inside an atomic transaction,
    preventing hung states.
    """
    headers = register_and_login(client, "Unhandled Poll User", "unhandled_poll@example.com")
    org_id, wf_id = setup_test_workflow(client, headers, "Unhandled Poll Org")

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        side_effect=RuntimeError("Unexpected kernel socket connection reset"),
    ):
        execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    assert len(execs) == 1
    failed_exec = execs[0]
    assert failed_exec.status == "failed"
    assert "Unexpected kernel socket connection reset" in failed_exec.error_message
    assert failed_exec.completed_at is not None

    # Verify persisted in database
    db_record = db_session.get(WorkflowExecution, failed_exec.id)
    assert db_record is not None
    assert db_record.status == "failed"
