from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.database.models import WorkflowExecution, WorkflowVersion
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.connectors.adapters.google_sheets import GoogleSheetsAdapter
from app.modules.executions.service import (
    execute_workflow,
    get_execution,
    retry_execution,
    run_retry_cycle,
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


def setup_multi_step_workflow(client, auth_headers: dict, org_name: str = "MultiStep Org") -> tuple[int, int]:
    # 1. Create org
    org_resp = client.post("/organizations", json={"name": org_name}, headers=auth_headers)
    org_id = org_resp.json()["id"]

    # 2. Add connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Multi Sheets",
            "config": {"spreadsheet_id": "multi_sheet_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_key_123"},
        },
        headers=auth_headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Multi CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_crm_456"},
        },
        headers=auth_headers,
    )

    # 3. Create workflow with 2 sequential action steps
    payload = {
        "name": "Sequential Flow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "multi_sheet_123"},
            },
            "steps": [
                {
                    "id": "step_1_create_lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {
                        "name": "trigger.values.Name",
                    },
                },
                {
                    "id": "step_2_append_confirmation",
                    "type": "action",
                    "connector": "google_sheets",
                    "action": "append_row",
                    "config": {"spreadsheet_id": "multi_sheet_123"},
                    "mapping": {
                        "row_values": {
                            "lead_id": "steps.step_1_create_lead.lead_id",
                            "status": "PROCESSED",
                        },
                    },
                },
            ],
        },
    }
    wf_resp = client.post("/workflows", json=payload, headers=auth_headers)
    wf_id = wf_resp.json()["id"]

    # 4. Publish v1
    client.post(f"/workflows/{wf_id}/publish", headers=auth_headers)
    return org_id, wf_id


# ============================================================================
# Tests: Module 6.2 Safe Retry Execution
# ============================================================================

def test_retry_preserves_exact_workflow_version_even_if_newer_published(client, db_session):
    headers = register_and_login(client, "Version User", "version_user@example.com")
    org_id, wf_id = setup_multi_step_workflow(client, headers, "Version Org")

    # Step 2 fails on v1 execution
    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=Exception("HTTP 503 Service Unavailable"),
    ):
        v1_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Anita"}},
            organization_id=org_id,
        )

    assert v1_exec.status == "failed"
    original_version_id = v1_exec.workflow_version_id

    # Now create and publish v2 of the workflow with updated definition
    edit_payload = {
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "multi_sheet_123"},
            },
            "steps": [
                {
                    "id": "step_1_create_lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {"name": "trigger.values.Name"},
                },
                {
                    "id": "step_2_v2_new_step",
                    "type": "action",
                    "connector": "crm",
                    "action": "update_lead",
                    "config": {},
                    "mapping": {"email": "trigger.values.Name"},
                },
            ],
        }
    }
    client.put(f"/workflows/{wf_id}", json=edit_payload, headers=headers)
    pub2_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub2_resp.status_code == 200

    # Ensure v2 version exists and is different from v1
    v2_version = db_session.query(WorkflowVersion).filter_by(workflow_id=wf_id, version_number=2).first()
    assert v2_version is not None
    assert v2_version.id != original_version_id

    # Retry the original v1 execution (Step 2 now succeeds)
    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        return_value={"appended": True, "row": 10},
    ):
        retry_exec = retry_execution(
            db=db_session,
            execution_id=v1_exec.id,
            organization_id=org_id,
        )

    # Invariant: The retry MUST execute the exact historical version (v1), NEVER v2!
    assert retry_exec.workflow_version_id == original_version_id
    assert retry_exec.workflow_version_id != v2_version.id
    assert retry_exec.retry_of_execution_id == v1_exec.id
    assert retry_exec.attempt_number == 2
    assert retry_exec.retry_count == 1
    assert retry_exec.status == "success"


def test_retry_from_failed_step_avoids_reexecuting_successful_steps(client, db_session):
    headers = register_and_login(client, "Resume User", "resume_user@example.com")
    org_id, wf_id = setup_multi_step_workflow(client, headers, "Resume Org")

    # Step 1 (CRM) succeeds; Step 2 (Google Sheets) fails
    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=Exception("HTTP 502 Bad Gateway"),
    ):
        v1_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Gaurav"}},
            organization_id=org_id,
        )

    assert v1_exec.status == "failed"
    step1_exec = v1_exec.step_executions[0]
    assert step1_exec.status == "success"
    step1_lead_id = step1_exec.output_data.get("lead_id")
    assert step1_lead_id is not None

    # On retry, mock CRMAdapter to ensure it is NOT CALLED AGAIN (side effect prevented)
    with patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=AssertionError("CRMAdapter should NOT be called for already successful step!"),
    ) as crm_spy, patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        return_value={"appended": True, "row": 15},
    ) as sheets_spy:
        retry_exec = retry_execution(
            db=db_session,
            execution_id=v1_exec.id,
            organization_id=org_id,
        )

    assert retry_exec.status == "success"
    assert crm_spy.call_count == 0  # Proves step 1 was reused, not re-executed
    assert sheets_spy.call_count == 1  # Step 2 was executed on retry

    # Verify step 1 in new execution has the preserved output data
    new_step1 = [s for s in retry_exec.step_executions if s.step_id == "step_1_create_lead"][0]
    assert new_step1.status == "success"
    assert new_step1.output_data.get("lead_id") == step1_lead_id


def test_retry_fails_if_workflow_is_paused(client, db_session):
    headers = register_and_login(client, "Pause User", "pause_user@example.com")
    org_id, wf_id = setup_multi_step_workflow(client, headers, "Pause Org")

    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=Exception("HTTP 429 Rate Limit"),
    ):
        failed_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Suresh"}},
            organization_id=org_id,
        )

    assert failed_exec.status == "failed"

    # Pause workflow
    client.post(f"/workflows/{wf_id}/pause", headers=headers)

    # Attempt retry
    with pytest.raises(ValueError, match="Workflow is not published or is paused"):
        retry_execution(db=db_session, execution_id=failed_exec.id, organization_id=org_id)


def test_retry_clears_next_retry_at_on_original(client, db_session):
    headers = register_and_login(client, "Clear Next User", "clear_next@example.com")
    org_id, wf_id = setup_multi_step_workflow(client, headers, "Clear Next Org")

    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=Exception("HTTP 429 Rate Limit"),
    ):
        failed_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Manish"}},
            organization_id=org_id,
        )

    assert failed_exec.next_retry_at is not None

    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        return_value={"appended": True},
    ):
        retry_exec = retry_execution(
            db=db_session,
            execution_id=failed_exec.id,
            organization_id=org_id,
        )

    # Refresh original execution and verify next_retry_at is cleared
    db_session.refresh(failed_exec)
    assert failed_exec.next_retry_at is None
    assert retry_exec.retry_of_execution_id == failed_exec.id


def test_run_retry_cycle_processes_due_retries(client, db_session):
    headers = register_and_login(client, "Cycle User", "cycle_user@example.com")
    org_id, wf_id = setup_multi_step_workflow(client, headers, "Cycle Org")

    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=Exception("HTTP 504 Gateway Timeout"),
    ):
        failed_exec = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data={"values": {"Name": "Prakash"}},
            organization_id=org_id,
        )

    assert failed_exec.status == "failed"
    # Manually set next_retry_at to 5 minutes ago to simulate it becoming due
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    failed_exec.next_retry_at = past_time
    db_session.commit()

    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        return_value={"appended": True},
    ):
        retried_list = run_retry_cycle(db=db_session)

    assert len(retried_list) >= 1
    matched = [r for r in retried_list if r.retry_of_execution_id == failed_exec.id]
    assert len(matched) == 1
    assert matched[0].status == "success"


def test_safe_retry_organization_isolation(client, db_session):
    headers_a = register_and_login(client, "Org A Safe", "org_a_safe@example.com")
    org_id_a, wf_id_a = setup_multi_step_workflow(client, headers_a, "Org A Safe")

    headers_b = register_and_login(client, "Org B Safe", "org_b_safe@example.com")
    org_id_b, _ = setup_multi_step_workflow(client, headers_b, "Org B Safe")

    with patch.object(
        GoogleSheetsAdapter,
        "execute_action",
        side_effect=Exception("HTTP 429 Rate Limit"),
    ):
        exec_a = execute_workflow(
            db=db_session,
            workflow_id=wf_id_a,
            trigger_data={"values": {"Name": "Org A"}},
            organization_id=org_id_a,
        )

    # Calling retry with Org B should fail
    with pytest.raises(ValueError, match="Execution not found"):
        retry_execution(db=db_session, execution_id=exec_a.id, organization_id=org_id_b)
