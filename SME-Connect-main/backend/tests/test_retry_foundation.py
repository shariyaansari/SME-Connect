from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import MagicMock

from app.core.security import encrypt_credentials
from app.database.models import (
    Connection,
    Membership,
    Organization,
    User,
    Workflow,
    WorkflowExecution,
    WorkflowVersion,
)
from app.modules.workflows.execution_service import (
    execute_workflow,
    get_execution,
    list_executions,
    to_execution_detail,
    to_execution_summary,
)
from app.modules.workflows.retry_policy import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAYS_SECONDS,
    FailureCategory,
    NON_RETRYABLE_CATEGORIES,
    RETRYABLE_CATEGORIES,
    calculate_next_retry_time,
    classify_failure,
    evaluate_retry,
    should_retry,
)


def _setup_org_user(db_session, email="retry_tester@example.com"):
    user = User(
        email=email,
        password_hash="pw",
        name="Retry Tester",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name="Retry Test Org")
    db_session.add(org)
    db_session.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=org.id,
        role="Admin",
    )
    db_session.add(membership)
    db_session.flush()
    return user, org, membership


def _create_published_workflow(db_session, user, org, action_connector="crm", action_slug="create_lead"):
    definition = {
        "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
        "steps": [
            {
                "id": "action-step",
                "type": "action",
                "connector": action_connector,
                "action": action_slug,
                "mapping": {"name": "trigger.values.Name"},
            }
        ],
    }

    wf = Workflow(
        organization_id=org.id,
        created_by=user.id,
        name="Retry Test Workflow",
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    version = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition=definition,
        created_by=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(version)
    db_session.flush()

    return wf, version


def _add_crm_connection(db_session, org):
    conn = Connection(
        organization_id=org.id,
        connector_slug="crm",
        name="CRM Connection",
        auth_type="api_key",
        config={"crm_provider": "HubSpot"},
        credentials=encrypt_credentials({"api_key": "pat_12345"}),
        status="active",
    )
    db_session.add(conn)
    db_session.flush()
    return conn


# ============================================================================
# 1. Retry Policy Unit Tests
# ============================================================================

def test_failure_classification():
    # Retryable errors
    assert classify_failure("Connection timed out after 30 seconds") == FailureCategory.TIMEOUT
    assert classify_failure("Rate limit exceeded: 429 Too Many Requests") == FailureCategory.RATE_LIMIT
    assert classify_failure("503 Service Unavailable: temporary connector failure") == FailureCategory.CONNECTOR_ERROR

    # Non-retryable errors
    assert classify_failure("Mapping resolution error: trigger.values.foo not found") == FailureCategory.MAPPING_ERROR
    assert classify_failure("No active connection found for connector 'crm'") == FailureCategory.AUTHENTICATION_ERROR
    assert classify_failure("401 Unauthorized: token expired") == FailureCategory.AUTHENTICATION_ERROR
    assert classify_failure("403 Forbidden: permission denied") == FailureCategory.AUTHORIZATION_ERROR
    assert classify_failure("Invalid input: 400 Bad Request") == FailureCategory.VALIDATION_ERROR
    assert classify_failure("Condition evaluation error: unsupported operator") == FailureCategory.CONDITION_ERROR


def test_retry_timing_and_backoff_calculation():
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    # Attempt 0 -> delay 60s
    t0 = calculate_next_retry_time(0, base_time=now)
    assert t0 == now + timedelta(seconds=60)

    # Attempt 1 -> delay 300s (5m)
    t1 = calculate_next_retry_time(1, base_time=now)
    assert t1 == now + timedelta(seconds=300)

    # Attempt 2 -> delay 900s (15m)
    t2 = calculate_next_retry_time(2, base_time=now)
    assert t2 == now + timedelta(seconds=900)

    # Attempt 3+ caps at last delay (900s)
    t3 = calculate_next_retry_time(3, base_time=now)
    assert t3 == now + timedelta(seconds=900)

    # Custom retry_after_seconds header
    t_custom = calculate_next_retry_time(0, base_time=now, retry_after_seconds=120)
    assert t_custom == now + timedelta(seconds=120)


def test_should_retry_policy():
    # Retryable categories allowed up to max_retries
    for cat in RETRYABLE_CATEGORIES:
        assert should_retry(cat, current_retry_count=0) is True
        assert should_retry(cat, current_retry_count=1) is True
        assert should_retry(cat, current_retry_count=2) is True
        assert should_retry(cat, current_retry_count=3) is False  # max reached

    # Non-retryable categories never allowed
    for cat in NON_RETRYABLE_CATEGORIES:
        assert should_retry(cat, current_retry_count=0) is False


def test_evaluate_retry_decisions():
    now = datetime.now(timezone.utc)

    # Case 1: Timeout (retryable) on first attempt
    d1 = evaluate_retry("Read timeout occurred", current_retry_count=0, base_time=now)
    assert d1.should_retry is True
    assert d1.failure_category == FailureCategory.TIMEOUT
    assert d1.retry_count == 1
    assert d1.next_retry_at is not None

    # Case 2: Max retries exceeded
    d2 = evaluate_retry("Read timeout occurred", current_retry_count=3, base_time=now)
    assert d2.should_retry is False
    assert d2.next_retry_at is None
    assert "Exceeded maximum retry count" in d2.reason

    # Case 3: Missing mapping (non-retryable)
    d3 = evaluate_retry("Mapping resolution error: invalid path", current_retry_count=0, base_time=now)
    assert d3.should_retry is False
    assert d3.failure_category == FailureCategory.MAPPING_ERROR
    assert d3.next_retry_at is None


# ============================================================================
# 2. Execution Engine Retry Integration Tests
# ============================================================================

def test_retryable_error_schedules_retry_on_workflow_execution(db_session, monkeypatch):
    user, org, _ = _setup_org_user(db_session, email="retry_sched@example.com")
    wf, _ = _create_published_workflow(db_session, user, org)
    _add_crm_connection(db_session, org)

    # Mock adapter to raise a transient timeout error
    from app.modules.connectors.registry import get_adapter
    adapter = get_adapter("crm")
    monkeypatch.setattr(
        adapter,
        "execute_action",
        MagicMock(side_effect=Exception("Connection timed out: 504 Gateway Timeout")),
    )

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"values": {"Name": "Test Customer"}},
        user_id=user.id,
    )

    assert execution.status == "failed"
    assert execution.failure_category in (FailureCategory.TIMEOUT.value, FailureCategory.CONNECTOR_ERROR.value)
    assert execution.next_retry_at is not None
    next_retry = execution.next_retry_at.replace(tzinfo=timezone.utc) if execution.next_retry_at.tzinfo is None else execution.next_retry_at
    assert next_retry > datetime.now(timezone.utc)
    assert execution.last_error_at is not None
    assert execution.attempt_number == 1
    assert execution.retry_count == 0


def test_non_retryable_error_does_not_schedule_retry(db_session):
    user, org, _ = _setup_org_user(db_session, email="noretry@example.com")
    # Workflow references CRM, but NO connection is added -> non-retryable Authentication/Config failure
    wf, _ = _create_published_workflow(db_session, user, org)

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"values": {"Name": "Test Customer"}},
        user_id=user.id,
    )

    assert execution.status == "failed"
    assert execution.failure_category == FailureCategory.AUTHENTICATION_ERROR.value
    assert execution.next_retry_at is None
    assert execution.last_error_at is not None


def test_mapping_error_is_classified_non_retryable(db_session):
    user, org, _ = _setup_org_user(db_session, email="mapping_err@example.com")
    wf, _ = _create_published_workflow(db_session, user, org)
    _add_crm_connection(db_session, org)

    # Pass payload missing mapped fields
    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"values": {}},  # missing "Name"
        user_id=user.id,
    )

    assert execution.status == "failed"
    assert execution.failure_category == FailureCategory.MAPPING_ERROR.value
    assert execution.next_retry_at is None


def test_maximum_retry_count_enforced_in_execution(db_session, monkeypatch):
    user, org, _ = _setup_org_user(db_session, email="max_retry@example.com")
    wf, _ = _create_published_workflow(db_session, user, org)
    _add_crm_connection(db_session, org)

    from app.modules.connectors.registry import get_adapter
    adapter = get_adapter("crm")
    monkeypatch.setattr(
        adapter,
        "execute_action",
        MagicMock(side_effect=Exception("Rate limit 429: Too Many Requests")),
    )

    # Run execution that already had 3 retries
    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"values": {"Name": "Test"}},
        user_id=user.id,
        attempt_number=4,
        retry_count=3,  # reached DEFAULT_MAX_RETRIES
    )

    assert execution.status == "failed"
    assert execution.failure_category == FailureCategory.RATE_LIMIT.value
    # Because retry_count == 3, next_retry_at MUST BE NONE
    assert execution.next_retry_at is None


def test_credentials_never_appear_in_retry_records(db_session, monkeypatch):
    user, org, _ = _setup_org_user(db_session, email="secret_test@example.com")
    wf, _ = _create_published_workflow(db_session, user, org)
    _add_crm_connection(db_session, org)

    from app.modules.connectors.registry import get_adapter
    adapter = get_adapter("crm")
    monkeypatch.setattr(
        adapter,
        "execute_action",
        MagicMock(side_effect=Exception("Temporary connector failure: 503")),
    )

    # Pass payload with sensitive secret keys
    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={
            "values": {"Name": "Alice"},
            "api_key": "raw_sensitive_key_9999",
            "client_secret": "raw_sensitive_secret_8888",
        },
        user_id=user.id,
    )

    assert execution.status == "failed"
    summary = to_execution_summary(execution)
    detail = to_execution_detail(execution)

    # Verify no raw secrets appear anywhere in summary, detail, or models
    raw_str = f"{summary.model_dump_json()} {detail.model_dump_json()}"
    assert "raw_sensitive_key_9999" not in raw_str
    assert "raw_sensitive_secret_8888" not in raw_str
    assert "••••••••" in raw_str
