import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import encrypt_credentials, hash_password
from app.database.connection import get_db
from app.database.models import (
    AuditLog,
    Connection,
    Membership,
    Organization,
    User,
    Workflow,
    WorkflowExecution,
    WorkflowStepExecution,
    WorkflowVersion,
)
from app.main import app
from app.modules.connectors.adapters.base import ConnectorExecutionError
from app.modules.workflows.execution_service import (
    execute_workflow,
    get_workflow_health,
    retry_workflow_execution,
)
from app.modules.workflows.idempotency import (
    generate_idempotency_key,
    is_event_duplicate,
    record_idempotency,
)
from app.modules.workflows.retry_policy import FailureCategory
from app.modules.workflows.scheduler_service import (
    is_schedule_due,
    run_scheduled_workflow_cycle,
    validate_timezone,
)


@pytest.fixture
def client(db_session):
    def _get_db():
        yield db_session
    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _setup_org_user(db_session, role="Admin", email_prefix="user"):
    unique_id = datetime.now().timestamp()
    user = User(
        name=f"Test {role}",
        email=f"{email_prefix}_{unique_id}@test.com",
        password_hash=hash_password("SecretPassword123!"),
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name=f"Test Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=org.id,
        role=role,
    )
    db_session.add(membership)
    db_session.flush()

    return user, org, membership


def _setup_connection(db_session, org_id, connector_slug="crm"):
    conn = Connection(
        organization_id=org_id,
        connector_slug=connector_slug,
        name=f"Active {connector_slug.upper()}",
        auth_type="api_key",
        config={"crm_provider": "HubSpot"},
        credentials=encrypt_credentials({"api_key": "secret_key_123"}),
        status="active",
    )
    db_session.add(conn)
    db_session.flush()
    return conn


# =========================================================================
# 1. Historical Version Preservation on Retry
# =========================================================================

def test_retry_preserves_historical_workflow_version(db_session):
    user, org, _ = _setup_org_user(db_session)
    _setup_connection(db_session, org.id, "crm")

    # 1. Create workflow and publish Version 1
    wf = Workflow(
        name="Multi-version Flow",
        organization_id=org.id,
        created_by=user.id,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    v1_def = {
        "trigger": {"connector": "google_sheets", "event": "new_row"},
        "steps": [
            {
                "id": "step_v1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {"name": "trigger.name_v1"},  # will fail if name_v1 missing
            }
        ],
    }
    v1 = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition=v1_def,
        created_by=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(v1)
    db_session.flush()

    # 2. Execute V1 with missing mapping -> fails
    failed_exec = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"irrelevant": "data"},
        organization_id=org.id,
    )
    assert failed_exec.status == "failed"
    assert failed_exec.workflow_version_id == v1.id
    assert failed_exec.attempt_number == 1

    # 3. Publish Version 2 with different steps
    v2_def = {
        "trigger": {"connector": "google_sheets", "event": "new_row"},
        "steps": [
            {
                "id": "step_v2",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {"name": "trigger.name_v2"},
            }
        ],
    }
    v2 = WorkflowVersion(
        workflow_id=wf.id,
        version_number=2,
        definition=v2_def,
        created_by=user.id,
        published_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    db_session.add(v2)
    db_session.flush()

    # 4. Retry the failed V1 execution
    retried_exec = retry_workflow_execution(
        db=db_session,
        execution_id=failed_exec.id,
        organization_id=org.id,
    )

    # 5. Verify retry executed against historical V1, NOT latest V2
    assert retried_exec.workflow_version_id == v1.id
    assert retried_exec.attempt_number == 2
    assert retried_exec.retry_of_execution_id == failed_exec.id
    assert retried_exec.retry_count == 1


def test_retry_rejected_for_paused_or_successful_workflow(db_session):
    user, org, _ = _setup_org_user(db_session)
    _setup_connection(db_session, org.id, "crm")

    wf = Workflow(
        name="Status Test Flow",
        organization_id=org.id,
        created_by=user.id,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    v1_def = {
        "trigger": {"connector": "google_sheets", "event": "new_row"},
        "steps": [
            {
                "id": "c1",
                "type": "condition",
                "field": "trigger.hello",
                "operator": "equals",
                "value": "world",
            }
        ],
    }
    v1 = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition=v1_def,
        created_by=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(v1)
    db_session.flush()

    # Successful execution
    success_exec = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"hello": "world"},
        organization_id=org.id,
    )
    assert success_exec.status == "success"

    # Cannot retry a successful execution
    with pytest.raises(ValueError, match="Only failed executions can be retried"):
        retry_workflow_execution(db=db_session, execution_id=success_exec.id, organization_id=org.id)

    # Failed execution
    failed_exec = WorkflowExecution(
        workflow_id=wf.id,
        workflow_version_id=v1.id,
        organization_id=org.id,
        status="failed",
        trigger_data={"test": "data"},
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(failed_exec)
    db_session.flush()

    # Pause workflow
    wf.status = "paused"
    db_session.flush()

    # Cannot retry when workflow is paused
    with pytest.raises(ValueError, match="paused workflow"):
        retry_workflow_execution(db=db_session, execution_id=failed_exec.id, organization_id=org.id)


# =========================================================================
# 2. Idempotency & Deduplication
# =========================================================================

def test_idempotency_key_generation_and_deduplication(db_session):
    user, org, _ = _setup_org_user(db_session)

    wf = Workflow(
        name="Dedupe Flow",
        organization_id=org.id,
        created_by=user.id,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    # Test candidate keys
    row_event = {"row_id": "ROW_4567", "data": "value"}
    key1 = generate_idempotency_key(row_event)
    assert key1 == "evt:ROW_4567"

    stripe_event = {"idempotency_key": "evt_charge_999", "amount": 5000}
    key2 = generate_idempotency_key(stripe_event)
    assert key2 == "evt:evt_charge_999"

    # Fallback SHA-256 for events without explicit ID
    arbitrary_event = {"temperature": 72.5, "city": "New York"}
    key3 = generate_idempotency_key(arbitrary_event)
    assert key3.startswith("hash:")

    # Check initially not duplicate
    assert is_event_duplicate(db_session, wf.id, key1) is False

    # Record idempotency
    record_idempotency(
        db=db_session,
        workflow_id=wf.id,
        organization_id=org.id,
        idempotency_key=key1,
        execution_id=101,
        event_payload=row_event,
    )

    # Now duplicate check must return True
    assert is_event_duplicate(db_session, wf.id, key1) is True
    # Different key is still not duplicate
    assert is_event_duplicate(db_session, wf.id, key2) is False


# =========================================================================
# 3. Scheduled Workflows & Scheduler Service
# =========================================================================

def test_timezone_validation():
    utc = validate_timezone("UTC")
    assert str(utc) == "UTC"

    ny = validate_timezone("America/New_York")
    assert str(ny) == "America/New_York"

    with pytest.raises(ValueError, match="Invalid timezone"):
        validate_timezone("Invalid/NonExistent_TZ")


def test_schedule_due_evaluation():
    # Hourly test
    utc_time = datetime(2026, 10, 6, 14, 25, 0, tzinfo=timezone.utc)
    hourly_cfg = {"frequency": "hourly", "minute": 20, "timezone": "UTC"}
    due, slot = is_schedule_due(hourly_cfg, utc_time)
    assert due is True
    assert slot == "hourly:2026-10-06-14"

    hourly_not_due_cfg = {"frequency": "hourly", "minute": 30, "timezone": "UTC"}
    due_not, _ = is_schedule_due(hourly_not_due_cfg, utc_time)
    assert due_not is False

    # Daily test with timezone
    # 14:25 UTC is 10:25 EDT in America/New_York
    daily_ny_cfg = {"frequency": "daily", "hour": 10, "minute": 0, "timezone": "America/New_York"}
    due_daily, slot_daily = is_schedule_due(daily_ny_cfg, utc_time)
    assert due_daily is True
    assert slot_daily == "daily:2026-10-06"

    daily_ny_future_cfg = {"frequency": "daily", "hour": 11, "minute": 0, "timezone": "America/New_York"}
    due_daily_not, _ = is_schedule_due(daily_ny_future_cfg, utc_time)
    assert due_daily_not is False


def test_scheduled_cycle_execution_and_slot_idempotency(db_session):
    user, org, _ = _setup_org_user(db_session)
    _setup_connection(db_session, org.id, "crm")

    wf = Workflow(
        name="Hourly Cron",
        organization_id=org.id,
        created_by=user.id,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    v1_def = {
        "trigger": {
            "connector": "schedule",
            "event": "scheduled",
            "config": {"frequency": "hourly", "minute": 0, "timezone": "UTC"},
        },
        "steps": [
            {
                "id": "c1",
                "type": "condition",
                "field": "trigger.frequency",
                "operator": "equals",
                "value": "hourly",
            }
        ],
    }
    v1 = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition=v1_def,
        created_by=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(v1)
    db_session.flush()

    cycle_time = datetime(2026, 10, 6, 12, 5, 0, tzinfo=timezone.utc)

    # First cycle run -> triggers execution
    runs_1 = run_scheduled_workflow_cycle(db_session, current_time=cycle_time, organization_id=org.id)
    assert len(runs_1) == 1
    assert runs_1[0].status == "success"
    assert runs_1[0].trigger_data["slot"] == "hourly:2026-10-06-12"

    # Second cycle run within same hour slot -> deduplicated, does NOT run again
    runs_2 = run_scheduled_workflow_cycle(db_session, current_time=cycle_time, organization_id=org.id)
    assert len(runs_2) == 0


# =========================================================================
# 4. Workflow Health Metrics Derivation
# =========================================================================

def test_workflow_health_derivation(db_session):
    user, org, _ = _setup_org_user(db_session)

    wf = Workflow(
        name="Health Flow",
        organization_id=org.id,
        created_by=user.id,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    v1 = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition={
            "trigger": {"connector": "schedule", "event": "scheduled"},
            "steps": [
                {
                    "id": "c1",
                    "type": "condition",
                    "field": "trigger.slot",
                    "operator": "is_not_empty",
                }
            ],
        },
        created_by=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(v1)
    db_session.flush()

    # Never run
    h_init = get_workflow_health(db_session, wf.id, organization_id=org.id)
    assert h_init["status"] == "never_run"
    assert h_init["total_executions"] == 0

    # Record 3 successful executions
    for _ in range(3):
        e = WorkflowExecution(
            workflow_id=wf.id,
            workflow_version_id=v1.id,
            organization_id=org.id,
            status="success",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(e)
    db_session.flush()

    h_healthy = get_workflow_health(db_session, wf.id, organization_id=org.id)
    assert h_healthy["status"] == "healthy"
    assert h_healthy["success_rate_percent"] == 100.0

    # Record 2 consecutive failures
    for _ in range(2):
        ef = WorkflowExecution(
            workflow_id=wf.id,
            workflow_version_id=v1.id,
            organization_id=org.id,
            status="failed",
            error_message="CRM API 500 error",
            started_at=datetime.now(timezone.utc),
        )
        db_session.add(ef)
    db_session.flush()

    h_att = get_workflow_health(db_session, wf.id, organization_id=org.id)
    assert h_att["status"] == "needs_attention"
    assert h_att["consecutive_failures"] == 2

    # Record active scheduled retry in future
    e_retry = WorkflowExecution(
        workflow_id=wf.id,
        workflow_version_id=v1.id,
        organization_id=org.id,
        status="failed",
        error_message="Rate limit 429",
        next_retry_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(e_retry)
    db_session.flush()

    h_retrying = get_workflow_health(db_session, wf.id, organization_id=org.id)
    assert h_retrying["status"] == "retrying"
    assert h_retrying["is_retrying"] is True


# =========================================================================
# 5. Execution Safety Limits
# =========================================================================

def test_execution_safety_payload_and_step_limits(db_session):
    user, org, _ = _setup_org_user(db_session)

    wf = Workflow(
        name="Safety Limit Flow",
        organization_id=org.id,
        created_by=user.id,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    # Step limit: 51 steps exceeds MAX_WORKFLOW_STEPS (50)
    oversized_steps = [
        {
            "id": f"step_{i}",
            "type": "condition",
            "field": "trigger.val",
            "operator": "equals",
            "value": 1,
        }
        for i in range(51)
    ]
    v_too_many = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition={"trigger": {"connector": "google_sheets", "event": "new_row"}, "steps": oversized_steps},
        created_by=user.id,
        published_at=datetime.now(timezone.utc),
    )
    db_session.add(v_too_many)
    db_session.flush()

    with pytest.raises(ValueError, match="maximum allowed steps"):
        execute_workflow(db_session, wf.id, {"val": 1}, organization_id=org.id)

    # Valid step count version
    v_ok = WorkflowVersion(
        workflow_id=wf.id,
        version_number=2,
        definition={
            "trigger": {"connector": "google_sheets", "event": "new_row"},
            "steps": [
                {
                    "id": "step_c",
                    "type": "condition",
                    "field": "trigger.val",
                    "operator": "equals",
                    "value": 1,
                }
            ],
        },
        created_by=user.id,
        published_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    db_session.add(v_ok)
    db_session.flush()

    # Payload size limit: payload > 1MB
    huge_payload = {"massive_field": "X" * 1_050_000}
    with pytest.raises(ValueError, match="exceeds maximum allowed size"):
        execute_workflow(db_session, wf.id, huge_payload, organization_id=org.id)


# =========================================================================
# 6. Manual Retry & Workflow Health API Endpoints
# =========================================================================

def test_manual_retry_api_and_rbac(client, db_session):
    # Setup Admin user
    admin_reg = client.post(
        "/auth/register",
        json={"name": "Admin Tester", "email": "admin_rel@test.com", "password": "Password123!"},
    )
    client.post("/auth/verify-email", json={"token": admin_reg.json()["verification_token"]})
    admin_login = client.post(
        "/auth/login",
        json={"email": "admin_rel@test.com", "password": "Password123!"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    # Setup Viewer user in same org
    viewer_reg = client.post(
        "/auth/register",
        json={"name": "Viewer Tester", "email": "viewer_rel@test.com", "password": "Password123!"},
    )
    client.post("/auth/verify-email", json={"token": viewer_reg.json()["verification_token"]})
    viewer_login = client.post(
        "/auth/login",
        json={"email": "viewer_rel@test.com", "password": "Password123!"},
    )
    viewer_headers = {"Authorization": f"Bearer {viewer_login.json()['access_token']}"}

    # Create Organization under Admin
    org_resp = client.post("/organizations", json={"name": "Reliability Org"}, headers=admin_headers)
    org_id = org_resp.json()["id"]

    # Invite viewer as Viewer
    inv_resp = client.post(
        "/organizations/invitations",
        json={"email": "viewer_rel@test.com", "role": "Viewer"},
        headers=admin_headers,
    )
    client.post(
        "/organizations/invitations/accept",
        json={"token": inv_resp.json()["token"]},
        headers=viewer_headers,
    )

    # Add Google Sheets connection
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Google Sheets",
            "auth_type": "api_key",
            "config": {"spreadsheet_id": "test_sheet_id"},
            "credentials": {"client_id": "cid", "client_secret": "csec"},
        },
        headers=admin_headers,
    )

    # Add CRM connection
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "CRM",
            "auth_type": "api_key",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat-valid"},
        },
        headers=admin_headers,
    )

    # Create workflow that fails on execution
    wf_resp = client.post(
        "/workflows",
        json={
            "name": "Retry Endpoint Flow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [
                    {
                        "id": "failing_step",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "mapping": {"name": "trigger.non_existent_key"},
                    }
                ],
            },
        },
        headers=admin_headers,
    )
    wf_id = wf_resp.json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=admin_headers)

    # Execute flow -> fails
    exec_resp = client.post(
        f"/workflows/{wf_id}/execute",
        json={"trigger_data": {"other_field": 123}},
        headers=admin_headers,
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    exec_id = exec_data["id"]
    assert exec_data["status"] == "failed"

    # Viewer tries to retry -> 403 Forbidden
    retry_viewer_resp = client.post(f"/executions/{exec_id}/retry", headers=viewer_headers)
    assert retry_viewer_resp.status_code == 403
    assert "Viewers are not permitted" in retry_viewer_resp.json()["detail"]

    # Admin retries -> 200 OK
    retry_admin_resp = client.post(f"/executions/{exec_id}/retry", headers=admin_headers)
    assert retry_admin_resp.status_code == 200
    retry_data = retry_admin_resp.json()
    assert retry_data["attempt_number"] == 2
    assert retry_data["retry_of_execution_id"] == exec_id
    assert retry_data["retry_count"] == 1

    # Verify Audit Log entry created for the retry
    audit_logs = db_session.scalars(
        select(AuditLog).where(
            AuditLog.organization_id == org_id,
            AuditLog.action == "WORKFLOW_EXECUTION_RETRIED",
        )
    ).all()
    assert len(list(audit_logs)) >= 1

    # Test Workflow Health Endpoint
    health_resp = client.get(f"/workflows/{wf_id}/health", headers=admin_headers)
    assert health_resp.status_code == 200
    h_data = health_resp.json()
    assert h_data["workflow_id"] == wf_id
    assert h_data["total_executions"] >= 2
    assert "status" in h_data
