from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.database.models import AuditLog, WorkflowExecution
from app.modules.connectors.adapters.base import ConnectorExecutionError
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.connectors.adapters.google_sheets import GoogleSheetsAdapter
from app.modules.executions.retry_policy import explain_failure_for_user
from app.modules.executions.safety_limits import (
    MAX_EXECUTION_DURATION_SECONDS,
    MAX_PAYLOAD_BYTES,
    MAX_WORKFLOW_STEPS,
)
from app.modules.executions.service import (
    execute_workflow,
    retry_execution,
    to_detail_response,
)
from app.modules.workflows.health import (
    WorkflowHealthStatus,
    calculate_workflow_health,
)
from app.modules.workflows.validation import validate_workflow_definition


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


def setup_observability_workflow(client, auth_headers: dict, org_name: str = "Obs Org") -> tuple[int, int]:
    # 1. Create org
    org_resp = client.post("/organizations", json={"name": org_name}, headers=auth_headers)
    org_id = org_resp.json()["id"]

    # 2. Add connection
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Obs CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_key_obs_123"},
        },
        headers=auth_headers,
    )

    # 3. Create workflow
    payload = {
        "name": "Reliability Lead Pipeline",
        "definition": {
            "trigger": {
                "type": "schedule",
                "event": "scheduled",
                "config": {"frequency": "daily", "time": "10:00", "timezone": "UTC"},
            },
            "steps": [
                {
                    "id": "step_create_lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {"name": "trigger.name"},
                }
            ],
        },
    }
    wf_resp = client.post("/workflows", json=payload, headers=auth_headers)
    wf_id = wf_resp.json()["id"]

    # 4. Publish
    client.post(f"/workflows/{wf_id}/publish", headers=auth_headers)
    return org_id, wf_id


# ============================================================================
# Tests: Module 6.7 Workflow Health
# ============================================================================

def test_workflow_health_states(client, db_session):
    headers = register_and_login(client, "Health User", "health@example.com")
    org_id, wf_id = setup_observability_workflow(client, headers, "Health Org")

    # 1. Never run
    health_never = calculate_workflow_health(db_session, wf_id, org_id)
    assert health_never.health_status == WorkflowHealthStatus.NEVER_RUN
    assert "ready to run" in health_never.health_message

    # 2. Healthy after successful run
    with patch.object(CRMAdapter, "execute_action", return_value={"lead_id": "101"}):
        execute_workflow(db_session, wf_id, trigger_data={"name": "Good Lead"}, organization_id=org_id)

    health_good = calculate_workflow_health(db_session, wf_id, org_id)
    assert health_good.health_status == WorkflowHealthStatus.HEALTHY
    assert health_good.recent_success_rate == 100.0
    assert health_good.consecutive_failures == 0

    # 3. Needs attention after failed run (non-retryable)
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("401 Unauthorized")):
        execute_workflow(db_session, wf_id, trigger_data={"name": "Bad Lead"}, organization_id=org_id)

    health_bad = calculate_workflow_health(db_session, wf_id, org_id)
    assert health_bad.health_status == WorkflowHealthStatus.NEEDS_ATTENTION
    assert health_bad.consecutive_failures == 1
    assert "Authorization Required" in health_bad.health_message

    # 4. Retrying when failure has next_retry_at scheduled in the future
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("429 Too Many Requests")):
        retrying_exec = execute_workflow(db_session, wf_id, trigger_data={"name": "Rate Lead"}, organization_id=org_id)

    assert retrying_exec.next_retry_at is not None
    health_retrying = calculate_workflow_health(db_session, wf_id, org_id)
    assert health_retrying.health_status == WorkflowHealthStatus.RETRYING
    assert health_retrying.is_retrying is True

    # 5. Paused workflow
    client.post(f"/workflows/{wf_id}/pause", headers=headers)
    health_paused = calculate_workflow_health(db_session, wf_id, org_id)
    assert health_paused.health_status == WorkflowHealthStatus.PAUSED


def test_workflow_health_api_endpoint(client, db_session):
    headers = register_and_login(client, "Health API User", "health_api@example.com")
    org_id, wf_id = setup_observability_workflow(client, headers, "Health API Org")

    resp = client.get(f"/workflows/{wf_id}/health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["workflow_id"] == wf_id
    assert data["health_status"] == "never_run"


# ============================================================================
# Tests: Module 6.8 Error Experience
# ============================================================================

def test_error_experience_human_friendly_explanations(client, db_session):
    headers = register_and_login(client, "Error UX User", "error_ux@example.com")
    org_id, wf_id = setup_observability_workflow(client, headers, "Error UX Org")

    # Fail with 401
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("401 Unauthorized: Invalid API token"),
    ):
        exec_record = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"name": "Test UX"},
            organization_id=org_id,
        )

    assert exec_record.status == "failed"
    detail = to_detail_response(exec_record)

    # Verify safe human-friendly error details
    assert detail.failure_title == "Connection Authorization Required"
    assert "token may have expired" in (detail.failure_explanation or "")
    assert "Integrations" in (detail.actionable_guidance or "")
    assert detail.can_manual_retry is True
    # Verify no tokens leaked in failure messages
    assert "api_key" not in (detail.error_message or "").lower() or "••••••••" in (detail.error_message or "")


# ============================================================================
# Tests: Module 6.9 Rate Limit & Connector Failure Handling
# ============================================================================

def test_connector_execution_error_contract(client, db_session):
    headers = register_and_login(client, "Contract User", "contract@example.com")
    org_id, wf_id = setup_observability_workflow(client, headers, "Contract Org")

    # Adapter raises standardized ConnectorExecutionError contract
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=ConnectorExecutionError(
            message="HubSpot API rate limit exceeded (100 req/10s)",
            category="rate_limit",
            retryable=True,
            provider_code="RATE_LIMIT_EXCEEDED",
        ),
    ):
        exec_record = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"name": "Contract Lead"},
            organization_id=org_id,
        )

    assert exec_record.status == "failed"
    assert exec_record.failure_category == "rate_limit"
    assert exec_record.next_retry_at is not None  # Retryable contract schedules retry


# ============================================================================
# Tests: Module 6.10 Execution Safety Limits
# ============================================================================

def test_execution_safety_payload_size_limit(client, db_session):
    headers = register_and_login(client, "Safety User", "safety@example.com")
    org_id, wf_id = setup_observability_workflow(client, headers, "Safety Org")

    # Oversized payload exceeding MAX_PAYLOAD_BYTES (500 KB)
    huge_payload = {"name": "X" * (MAX_PAYLOAD_BYTES + 1000)}

    with pytest.raises(ValueError, match="exceeds maximum permitted safety limit"):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data=huge_payload,
            organization_id=org_id,
        )


def test_execution_safety_step_count_limit():
    # Construct workflow with steps exceeding MAX_WORKFLOW_STEPS (50)
    huge_steps = [
        {
            "id": f"step_{i}",
            "type": "action",
            "connector": "crm",
            "action": "create_lead",
            "config": {},
            "mapping": {"name": "trigger.name"},
        }
        for i in range(MAX_WORKFLOW_STEPS + 1)
    ]
    wf_def = {
        "name": "Huge Workflow",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "daily", "time": "10:00", "timezone": "UTC"}},
        "steps": huge_steps,
    }

    res = validate_workflow_definition(wf_def)
    assert res.valid is False
    assert any("exceeds maximum allowed steps" in e.message for e in res.errors)


# ============================================================================
# Tests: Module 6.11 Reliability Audit Events
# ============================================================================

def test_reliability_audit_logging(client, db_session):
    headers = register_and_login(client, "Audit User", "audit@example.com")
    org_id, wf_id = setup_observability_workflow(client, headers, "Audit Org")

    # 1. Success execution produces WORKFLOW_EXECUTION_SUCCEEDED audit log
    with patch.object(CRMAdapter, "execute_action", return_value={"lead_id": "aud_1"}):
        success_exec = execute_workflow(db_session, wf_id, {"name": "Audit Succeeded"}, organization_id=org_id)

    succ_logs = (
        db_session.query(AuditLog)
        .filter_by(organization_id=org_id, action="WORKFLOW_EXECUTION_SUCCEEDED")
        .all()
    )
    assert len(succ_logs) >= 1
    assert any(l.resource_id == success_exec.id for l in succ_logs)

    # 2. Failure execution produces WORKFLOW_RETRY_SCHEDULED audit log
    with patch.object(CRMAdapter, "execute_action", side_effect=Exception("HTTP 429 Too Many Requests")):
        fail_exec = execute_workflow(db_session, wf_id, {"name": "Audit Failed"}, organization_id=org_id)

    sched_logs = (
        db_session.query(AuditLog)
        .filter_by(organization_id=org_id, action="WORKFLOW_RETRY_SCHEDULED")
        .all()
    )
    assert len(sched_logs) >= 1
    assert any(l.resource_id == fail_exec.id for l in sched_logs)

    # 3. Manual retry produces WORKFLOW_EXECUTION_RETRIED audit log
    with patch.object(CRMAdapter, "execute_action", return_value={"lead_id": "aud_retried"}):
        retry_exec = retry_execution(db_session, fail_exec.id, organization_id=org_id)

    retry_logs = (
        db_session.query(AuditLog)
        .filter_by(organization_id=org_id, action="WORKFLOW_EXECUTION_RETRIED")
        .all()
    )
    assert len(retry_logs) >= 1
    assert any(l.resource_id == retry_exec.id for l in retry_logs)
