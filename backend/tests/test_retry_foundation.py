from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.database.models import WorkflowExecution
from app.modules.executions.retry_policy import (
    MAX_RETRY_COUNT,
    RETRY_DELAYS_SECONDS,
    FailureCategory,
    calculate_next_retry,
    classify_failure,
    is_category_retryable,
)
from app.modules.executions.service import (
    execute_workflow,
    get_execution,
    list_executions,
    to_detail_response,
    to_summary_response,
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


# ============================================================================
# Unit Tests: Retry Policy & Failure Categorization (6.1)
# ============================================================================

def test_failure_classification_retryable_errors():
    # 429 Rate limit
    cat, retryable = classify_failure(Exception("HTTP 429 Too Many Requests: Rate limit exceeded"))
    assert cat == FailureCategory.RATE_LIMIT
    assert retryable is True

    # Timeout
    cat, retryable = classify_failure(TimeoutError("ReadTimeout: Connection timed out to provider"))
    assert cat == FailureCategory.TIMEOUT
    assert retryable is True

    # 503 Service unavailable
    cat, retryable = classify_failure(Exception("503 Service Unavailable: upstream connection reset"))
    assert cat == FailureCategory.CONNECTOR_ERROR
    assert retryable is True


def test_failure_classification_non_retryable_errors():
    # 401 Unauthorized / credentials invalid
    cat, retryable = classify_failure(Exception("401 Unauthorized: Invalid API key provided"))
    assert cat == FailureCategory.AUTHENTICATION_ERROR
    assert retryable is False

    # 403 Forbidden
    cat, retryable = classify_failure(Exception("403 Forbidden: Permission denied for resource"))
    assert cat == FailureCategory.AUTHORIZATION_ERROR
    assert retryable is False

    # Mapping error
    cat, retryable = classify_failure(ValueError("Mapping path 'trigger.missing_field' not found in trigger data"))
    assert cat == FailureCategory.MAPPING_ERROR
    assert retryable is False

    # Condition evaluation configuration error
    cat, retryable = classify_failure(ValueError("Unsupported condition operator 'unknown_op'"))
    assert cat == FailureCategory.CONDITION_ERROR
    assert retryable is False

    # Missing connection
    cat, retryable = classify_failure(ValueError("No active connection found for connector 'crm' in this organization"))
    assert cat == FailureCategory.VALIDATION_ERROR
    assert retryable is False


def test_retry_timing_and_bounded_backoff():
    base_time = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)

    # Attempt 0 -> 1st retry in 60s
    retry_0 = calculate_next_retry(0, from_time=base_time)
    assert retry_0 == base_time + timedelta(seconds=60)

    # Attempt 1 -> 2nd retry in 300s (5 mins)
    retry_1 = calculate_next_retry(1, from_time=base_time)
    assert retry_1 == base_time + timedelta(seconds=300)

    # Attempt 2 -> 3rd retry in 900s (15 mins)
    retry_2 = calculate_next_retry(2, from_time=base_time)
    assert retry_2 == base_time + timedelta(seconds=900)

    # Attempt 3 -> Bounded limit reached, no more retries
    retry_3 = calculate_next_retry(3, from_time=base_time)
    assert retry_3 is None

    # Beyond limit
    assert calculate_next_retry(4, from_time=base_time) is None


# ============================================================================
# Integration Tests: Retry Foundation on Workflow Executions (6.1)
# ============================================================================

def setup_published_workflow(client, auth_headers: dict, org_name: str = "Retry Org") -> tuple[int, int]:
    # 1. Create organization
    org_resp = client.post("/organizations", json={"name": org_name}, headers=auth_headers)
    org_id = org_resp.json()["id"]

    # 2. Add connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Retry Sheets",
            "config": {"spreadsheet_id": "retry_sheet_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_secret_key_123"},
        },
        headers=auth_headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Retry CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "super_secret_crm_key"},
        },
        headers=auth_headers,
    )

    # 3. Create workflow
    payload = {
        "name": "Retryable Workflow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "retry_sheet_123"},
            },
            "steps": [
                {
                    "id": "create-lead-step",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {
                        "name": "trigger.values.Name",
                    },
                },
            ],
        },
    }
    wf_resp = client.post("/workflows", json=payload, headers=auth_headers)
    wf_id = wf_resp.json()["id"]

    # 4. Publish workflow
    client.post(f"/workflows/{wf_id}/publish", headers=auth_headers)
    return org_id, wf_id


def test_retryable_error_schedules_retry(client, db_session):
    headers = register_and_login(client, "Retry User 1", "retry1@example.com")
    org_id, wf_id = setup_published_workflow(client, headers)

    trigger_data = {"values": {"Name": "Siddharth"}}

    # Mock CRM adapter execute_action to fail with 429 Rate Limit
    from app.modules.connectors.adapters.crm import CRMAdapter

    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("HTTP 429 Too Many Requests: Rate limit exceeded"),
    ):
        execution = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data=trigger_data,
            organization_id=org_id,
        )

    assert execution.status == "failed"
    assert execution.failure_category == "rate_limit"
    assert execution.attempt_number == 1
    assert execution.retry_count == 0
    assert execution.next_retry_at is not None
    assert execution.last_error_at is not None

    # Verify next_retry_at is roughly 60s in future
    expected_delay = (execution.next_retry_at - execution.last_error_at).total_seconds()
    assert abs(expected_delay - 60) < 5

    # Check step execution
    assert len(execution.step_executions) == 1
    step_exec = execution.step_executions[0]
    assert step_exec.status == "failed"
    assert step_exec.failure_category == "rate_limit"


def test_non_retryable_error_does_not_schedule_retry(client, db_session):
    headers = register_and_login(client, "Retry User 2", "retry2@example.com")
    org_id, wf_id = setup_published_workflow(client, headers)

    trigger_data = {"values": {"Name": "Pooja"}}

    from app.modules.connectors.adapters.crm import CRMAdapter

    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("401 Unauthorized: Invalid API token"),
    ):
        execution = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data=trigger_data,
            organization_id=org_id,
        )

    assert execution.status == "failed"
    assert execution.failure_category == "authentication_error"
    assert execution.attempt_number == 1
    assert execution.retry_count == 0
    assert execution.next_retry_at is None  # Non-retryable error must NOT schedule retry
    assert execution.last_error_at is not None


def test_maximum_retry_count_enforced(client, db_session):
    headers = register_and_login(client, "Retry User 3", "retry3@example.com")
    org_id, wf_id = setup_published_workflow(client, headers)

    trigger_data = {"values": {"Name": "Kavita"}}

    from app.modules.connectors.adapters.crm import CRMAdapter

    # Attempt with retry_count = 3 (which is MAX_RETRY_COUNT)
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("HTTP 429 Too Many Requests: Rate limit exceeded"),
    ):
        execution = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data=trigger_data,
            organization_id=org_id,
            attempt_number=4,
            retry_count=3,
        )

    assert execution.status == "failed"
    assert execution.failure_category == "rate_limit"
    assert execution.attempt_number == 4
    assert execution.retry_count == 3
    # Exceeded max retry count, so next_retry_at MUST be None
    assert execution.next_retry_at is None


def test_credentials_never_appear_in_retry_records(client, db_session):
    headers = register_and_login(client, "Retry User 4", "retry4@example.com")
    org_id, wf_id = setup_published_workflow(client, headers)

    trigger_data = {"values": {"Name": "Secret Holder"}}

    from app.modules.connectors.adapters.crm import CRMAdapter

    # Error message containing leaked token from hypothetical upstream
    leak_msg = "Error contacting CRM with api_key 'super_secret_crm_key' and secret 'sec_secret_key_123'"
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception(leak_msg),
    ):
        execution = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data=trigger_data,
            organization_id=org_id,
        )

    assert execution.status == "failed"
    # Verify sanitized execution error message
    assert "super_secret_crm_key" not in execution.error_message
    assert "sec_secret_key_123" not in execution.error_message

    # Verify step execution error message
    step_exec = execution.step_executions[0]
    assert "super_secret_crm_key" not in step_exec.error_message
    assert "sec_secret_key_123" not in step_exec.error_message

    # Verify detail response
    detail = to_detail_response(execution)
    assert "super_secret_crm_key" not in (detail.error_message or "")
    assert "sec_secret_key_123" not in (detail.error_message or "")


def test_retry_organization_isolation(client, db_session):
    headers_a = register_and_login(client, "Org A User", "org_a@example.com")
    org_id_a, wf_id_a = setup_published_workflow(client, headers_a, "Org A Unique")

    headers_b = register_and_login(client, "Org B User", "org_b@example.com")
    org_id_b, wf_id_b = setup_published_workflow(client, headers_b, "Org B Unique")

    from app.modules.connectors.adapters.crm import CRMAdapter

    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("HTTP 429 Too Many Requests"),
    ):
        exec_a = execute_workflow(
            db=db_session,
            workflow_id=wf_id_a,
            trigger_data={"values": {"Name": "A"}},
            organization_id=org_id_a,
        )

    # Querying execution from Org B must fail
    with pytest.raises(ValueError, match="Execution not found"):
        get_execution(db=db_session, execution_id=exec_a.id, organization_id=org_id_b)

    # Executions list for Org B must not contain Org A's execution
    b_executions = list_executions(db=db_session, organization_id=org_id_b)
    assert exec_a.id not in [e.id for e in b_executions]
