from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.database.models import WorkflowExecution
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.executions.scheduler import (
    compute_schedule_due_state,
    run_scheduled_workflow_cycle,
)
from app.modules.executions.service import execute_workflow
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


# ============================================================================
# Unit Tests: Schedule Definition Validation & Timezone Handling (Module 6.4)
# ============================================================================

def test_valid_schedule_definitions():
    # 1. Valid Hourly
    wf_hourly = {
        "name": "Hourly Sync",
        "trigger": {
            "type": "schedule",
            "event": "scheduled",
            "config": {
                "frequency": "hourly",
                "minute": 15,
                "timezone": "UTC",
            },
        },
        "steps": [
            {
                "id": "step1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "config": {"name": "Hourly Lead"},
            }
        ],
    }
    assert validate_workflow_definition(wf_hourly).valid is True

    # 2. Valid Daily
    wf_daily = {
        "name": "Daily Sync",
        "trigger": {
            "type": "schedule",
            "event": "scheduled",
            "config": {
                "frequency": "daily",
                "time": "09:30",
                "timezone": "Asia/Kolkata",
            },
        },
        "steps": [
            {
                "id": "step1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "config": {"name": "Daily Lead"},
            }
        ],
    }
    assert validate_workflow_definition(wf_daily).valid is True

    # 3. Valid Weekly
    wf_weekly = {
        "name": "Weekly Sync",
        "trigger": {
            "type": "schedule",
            "event": "scheduled",
            "config": {
                "frequency": "weekly",
                "time": "18:00",
                "day_of_week": "friday",
                "timezone": "America/New_York",
            },
        },
        "steps": [
            {
                "id": "step1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "config": {"name": "Weekly Lead"},
            }
        ],
    }
    assert validate_workflow_definition(wf_weekly).valid is True


def test_invalid_schedule_definitions():
    base_step = [
        {
            "id": "step1",
            "type": "action",
            "connector": "crm",
            "action": "create_lead",
            "config": {"name": "Lead"},
        }
    ]

    # Invalid frequency
    res = validate_workflow_definition({
        "name": "Bad Freq",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "monthly", "timezone": "UTC"}},
        "steps": base_step,
    })
    assert res.valid is False
    assert any(e.path == "trigger.config.frequency" for e in res.errors)

    # Invalid timezone
    res = validate_workflow_definition({
        "name": "Bad TZ",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "daily", "time": "09:00", "timezone": "Mars/Olympus"}},
        "steps": base_step,
    })
    assert res.valid is False
    assert any(e.path == "trigger.config.timezone" for e in res.errors)

    # Missing time for daily schedule
    res = validate_workflow_definition({
        "name": "Missing Time",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "daily", "timezone": "UTC"}},
        "steps": base_step,
    })
    assert res.valid is False
    assert any(e.path == "trigger.config.time" for e in res.errors)

    # Missing day_of_week for weekly schedule
    res = validate_workflow_definition({
        "name": "Missing DOW",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "weekly", "time": "09:00", "timezone": "UTC"}},
        "steps": base_step,
    })
    assert res.valid is False
    assert any(e.path == "trigger.config.day_of_week" for e in res.errors)


def test_schedule_due_state_timezone_computation():
    # 09:00 in Asia/Kolkata (+05:30) corresponds to 03:30 UTC
    cfg_kolkata = {
        "frequency": "daily",
        "time": "09:00",
        "timezone": "Asia/Kolkata",
    }

    # At 03:00 UTC (08:30 IST) -> not due yet
    ref_early = datetime(2026, 10, 8, 3, 0, 0, tzinfo=timezone.utc)
    _, is_due_early = compute_schedule_due_state(cfg_kolkata, ref_early)
    assert is_due_early is False

    # At 03:35 UTC (09:05 IST) -> due!
    ref_due = datetime(2026, 10, 8, 3, 35, 0, tzinfo=timezone.utc)
    period_key, is_due = compute_schedule_due_state(cfg_kolkata, ref_due)
    assert is_due is True
    # The calendar date in Kolkata is 2026-10-08
    assert period_key == "schedule:daily:2026-10-08"


# ============================================================================
# Integration Tests: Scheduler Service (Module 6.5)
# ============================================================================

def setup_scheduled_workflow(client, auth_headers: dict, org_name: str = "Sched Org", freq: str = "daily") -> tuple[int, int]:
    # 1. Create org
    org_resp = client.post("/organizations", json={"name": org_name}, headers=auth_headers)
    org_id = org_resp.json()["id"]

    # 2. Add connection for CRM action
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Sched CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_crm_999"},
        },
        headers=auth_headers,
    )

    # 3. Create scheduled workflow
    payload = {
        "name": "Morning Lead Generator",
        "definition": {
            "trigger": {
                "type": "schedule",
                "event": "scheduled",
                "config": {
                    "frequency": freq,
                    "time": "09:00",
                    "timezone": "Asia/Kolkata",
                },
            },
            "steps": [
                {
                    "id": "create-daily-report-lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {
                        "name": "Scheduled SME Task",
                        "email": "auto-daily@sme.com",
                    },
                }
            ],
        },
    }
    wf_resp = client.post("/workflows", json=payload, headers=auth_headers)
    wf_id = wf_resp.json()["id"]

    # 4. Publish workflow
    client.post(f"/workflows/{wf_id}/publish", headers=auth_headers)
    return org_id, wf_id


def test_published_scheduled_workflow_executes(client, db_session):
    headers = register_and_login(client, "Sched Runner", "runner@example.com")
    org_id, wf_id = setup_scheduled_workflow(client, headers)

    # 03:45 UTC is 09:15 IST (past 09:00 IST)
    ref_time = datetime(2026, 10, 8, 3, 45, 0, tzinfo=timezone.utc)

    with patch.object(
        CRMAdapter,
        "execute_action",
        return_value={"lead_id": "sched_lead_123"},
    ):
        execs = run_scheduled_workflow_cycle(
            db=db_session,
            reference_time=ref_time,
            organization_id=org_id,
        )

    assert len(execs) == 1
    assert execs[0].workflow_id == wf_id
    assert execs[0].organization_id == org_id
    assert execs[0].status == "success"
    assert execs[0].workflow_version_id is not None


def test_duplicate_scheduler_cycle_prevents_duplicate_executions(client, db_session):
    headers = register_and_login(client, "Dup Sched User", "dup_sched@example.com")
    org_id, wf_id = setup_scheduled_workflow(client, headers, "Dup Sched Org")

    ref_time = datetime(2026, 10, 8, 4, 0, 0, tzinfo=timezone.utc)

    with patch.object(
        CRMAdapter,
        "execute_action",
        return_value={"lead_id": "sched_lead_dup"},
    ):
        first_cycle = run_scheduled_workflow_cycle(db=db_session, reference_time=ref_time, organization_id=org_id)
        second_cycle = run_scheduled_workflow_cycle(db=db_session, reference_time=ref_time, organization_id=org_id)

    assert len(first_cycle) == 1
    # Idempotency: Second cycle for same schedule window runs 0 new executions
    assert len(second_cycle) == 0


def test_paused_and_draft_workflows_do_not_execute(client, db_session):
    headers = register_and_login(client, "Status User", "status_user@example.com")
    org_id, wf_id = setup_scheduled_workflow(client, headers, "Status Org")

    # 1. Pause the workflow
    client.post(f"/workflows/{wf_id}/pause", headers=headers)

    ref_time = datetime(2026, 10, 8, 4, 0, 0, tzinfo=timezone.utc)
    paused_execs = run_scheduled_workflow_cycle(db=db_session, reference_time=ref_time, organization_id=org_id)
    assert len(paused_execs) == 0  # Paused workflow must NOT execute

    # 2. Create another workflow in draft state
    draft_payload = {
        "name": "Draft Schedule Flow",
        "definition": {
            "trigger": {
                "type": "schedule",
                "event": "scheduled",
                "config": {"frequency": "daily", "time": "09:00", "timezone": "Asia/Kolkata"},
            },
            "steps": [
                {
                    "id": "step1",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {"name": "Draft Lead", "email": "draft@sme.com"},
                }
            ],
        },
    }
    client.post("/workflows", json=draft_payload, headers=headers)

    draft_execs = run_scheduled_workflow_cycle(db=db_session, reference_time=ref_time, organization_id=org_id)
    assert len(draft_execs) == 0  # Draft workflow must NOT execute


# ============================================================================
# Integration Tests: Manual Retry API Endpoint (Module 6.6)
# ============================================================================

def test_manual_retry_endpoint_success(client, db_session):
    headers = register_and_login(client, "Manual Retry User", "manual_retry@example.com")
    org_id, wf_id = setup_scheduled_workflow(client, headers, "Manual Retry Org")

    # Create a failed execution
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("HTTP 503 Upstream Error"),
    ):
        failed_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"manual": True},
            organization_id=org_id,
        )

    assert failed_exec.status == "failed"

    # Retry manually via POST /executions/{execution_id}/retry
    with patch.object(
        CRMAdapter,
        "execute_action",
        return_value={"lead_id": "crm_retried_manual"},
    ):
        retry_resp = client.post(
            f"/executions/{failed_exec.id}/retry",
            headers=headers,
        )

    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()
    assert retry_data["status"] == "success"
    assert retry_data["retry_of_execution_id"] == failed_exec.id
    assert retry_data["attempt_number"] == 2
    assert retry_data["retry_count"] == 1


def test_manual_retry_endpoint_rejects_successful_executions(client, db_session):
    headers = register_and_login(client, "Success Retry User", "success_retry@example.com")
    org_id, wf_id = setup_scheduled_workflow(client, headers, "Success Retry Org")

    with patch.object(
        CRMAdapter,
        "execute_action",
        return_value={"lead_id": "good_lead"},
    ):
        success_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"manual": True},
            organization_id=org_id,
        )

    assert success_exec.status == "success"

    # Retrying a successful execution must be rejected with 400 Bad Request
    retry_resp = client.post(
        f"/executions/{success_exec.id}/retry",
        headers=headers,
    )
    assert retry_resp.status_code == 400
    assert "only failed executions can be retried" in retry_resp.json()["detail"].lower()
