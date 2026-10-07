from unittest.mock import MagicMock, patch
import pytest

from app.database.models import WorkflowExecution, WorkflowTriggerEvent, WorkflowTriggerState
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.connectors.adapters.google_sheets import GoogleSheetsAdapter
from app.modules.executions.idempotency import (
    check_and_record_event,
    extract_event_key,
    link_event_execution,
)
from app.modules.executions.runner import poll_workflow_trigger
from app.modules.executions.service import retry_execution


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


def setup_trigger_workflow(client, auth_headers: dict, org_name: str = "Idem Org") -> tuple[int, int]:
    # 1. Create org
    org_resp = client.post("/organizations", json={"name": org_name}, headers=auth_headers)
    org_id = org_resp.json()["id"]

    # 2. Add connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Idem Sheets",
            "config": {"spreadsheet_id": "idem_sheet_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_key_123"},
        },
        headers=auth_headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Idem CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_crm_456"},
        },
        headers=auth_headers,
    )

    # 3. Create workflow
    payload = {
        "name": "Idempotent Lead Flow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "idem_sheet_123"},
            },
            "steps": [
                {
                    "id": "create-lead",
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

    # 4. Publish
    client.post(f"/workflows/{wf_id}/publish", headers=auth_headers)
    return org_id, wf_id


# ============================================================================
# Unit Tests: Event Key Extraction & Deduplication Check
# ============================================================================

def test_extract_event_key_priority():
    # Priority 1: Explicit idempotency key
    rec1 = {"idempotency_key": "custom_key_abc", "id": "123", "row_index": 5}
    assert extract_event_key(rec1) == "idempotency_key:custom_key_abc"

    # Priority 2: Event ID / ID
    rec2 = {"event_id": "evt_999", "row_index": 5}
    assert extract_event_key(rec2) == "event_id:evt_999"

    # Priority 3: Domain ID (e.g. row_index, lead_id)
    rec3 = {"row_index": 12, "values": {"Name": "Test"}}
    assert extract_event_key(rec3) == "row_index:12"

    # Priority 4: Fallback canonical hash
    rec4 = {"arbitrary_data": "sample", "num": 42}
    key4 = extract_event_key(rec4)
    assert key4.startswith("hash:")
    # Deterministic: same payload yields exact same hash key
    assert extract_event_key({"num": 42, "arbitrary_data": "sample"}) == key4


# ============================================================================
# Integration Tests: Idempotency & Duplicate Protection (Module 6.3)
# ============================================================================

def test_same_event_cannot_create_duplicate_execution(client, db_session):
    headers = register_and_login(client, "Dup User", "dup_user@example.com")
    org_id, wf_id = setup_trigger_workflow(client, headers, "Dup Org")

    incoming_records = [
        {"row_index": 101, "values": {"Name": "Arjun"}},
    ]

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(incoming_records, {"last_row": 101}),
    ):
        first_poll_execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    assert len(first_poll_execs) == 1
    assert first_poll_execs[0].status == "success"

    # Second poll returns the EXACT same event (e.g. provider redelivery or runner restart)
    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(incoming_records, {"last_row": 101}),
    ):
        second_poll_execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    # Idempotency guarantee: second poll skips duplicate event, 0 executions created!
    assert len(second_poll_execs) == 0

    # Ensure exactly 1 execution exists in database for this workflow
    total_execs = db_session.query(WorkflowExecution).filter_by(workflow_id=wf_id).all()
    assert len(total_execs) == 1


def test_different_events_create_separate_executions(client, db_session):
    headers = register_and_login(client, "Diff User", "diff_user@example.com")
    org_id, wf_id = setup_trigger_workflow(client, headers, "Diff Org")

    rec1 = [{"row_index": 201, "values": {"Name": "Nisha"}}]
    rec2 = [{"row_index": 202, "values": {"Name": "Rohit"}}]

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(rec1, {"last_row": 201}),
    ):
        execs_1 = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(rec2, {"last_row": 202}),
    ):
        execs_2 = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    assert len(execs_1) == 1
    assert len(execs_2) == 1
    assert execs_1[0].id != execs_2[0].id


def test_two_workflows_in_different_organizations_do_not_collide(client, db_session):
    headers_a = register_and_login(client, "Org A User", "org_a_idem@example.com")
    org_id_a, wf_id_a = setup_trigger_workflow(client, headers_a, "Org A Idem")

    headers_b = register_and_login(client, "Org B User", "org_b_idem@example.com")
    org_id_b, wf_id_b = setup_trigger_workflow(client, headers_b, "Org B Idem")

    # Identical external event received by both orgs (e.g. row_index: 500)
    event_payload = [{"row_index": 500, "values": {"Name": "Shared Key"}}]

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(event_payload, {"last_row": 500}),
    ):
        exec_a = poll_workflow_trigger(db=db_session, workflow_id=wf_id_a, organization_id=org_id_a)
        exec_b = poll_workflow_trigger(db=db_session, workflow_id=wf_id_b, organization_id=org_id_b)

    # Both workflows must process their event without collision
    assert len(exec_a) == 1
    assert len(exec_b) == 1
    assert exec_a[0].organization_id == org_id_a
    assert exec_b[0].organization_id == org_id_b


def test_same_trigger_event_for_different_workflows_remains_isolated(client, db_session):
    headers = register_and_login(client, "Multi Wf User", "multi_wf@example.com")
    org_id, wf_id_1 = setup_trigger_workflow(client, headers, "Multi Wf Org")

    # Create second workflow in same org
    payload_2 = {
        "name": "Second Workflow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "idem_sheet_123"},
            },
            "steps": [
                {
                    "id": "step_c",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {"name": "trigger.values.Name"},
                }
            ],
        },
    }
    wf_2_resp = client.post("/workflows", json=payload_2, headers=headers)
    wf_id_2 = wf_2_resp.json()["id"]
    client.post(f"/workflows/{wf_id_2}/publish", headers=headers)

    # Event with same ID
    event_payload = [{"row_index": 777, "values": {"Name": "Dual Workflow Lead"}}]

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(event_payload, {"last_row": 777}),
    ):
        execs_1 = poll_workflow_trigger(db=db_session, workflow_id=wf_id_1, organization_id=org_id)
        execs_2 = poll_workflow_trigger(db=db_session, workflow_id=wf_id_2, organization_id=org_id)

    # Both workflows are separate and must independently process the event
    assert len(execs_1) == 1
    assert len(execs_2) == 1


def test_retry_does_not_accidentally_become_a_new_trigger_event(client, db_session):
    headers = register_and_login(client, "Retry Idem User", "retry_idem@example.com")
    org_id, wf_id = setup_trigger_workflow(client, headers, "Retry Idem Org")

    # Polling fails during step execution
    event_payload = [{"row_index": 888, "values": {"Name": "Failing Lead"}}]

    with patch.object(
        GoogleSheetsAdapter,
        "read_trigger_data",
        return_value=(event_payload, {"last_row": 888}),
    ), patch.object(
        CRMAdapter,
        "execute_action",
        side_effect=Exception("HTTP 502 Bad Gateway"),
    ):
        failed_execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)

    assert len(failed_execs) == 1
    failed_exec = failed_execs[0]
    assert failed_exec.status == "failed"

    # Count trigger events before retry
    events_count_before = db_session.query(WorkflowTriggerEvent).filter_by(workflow_id=wf_id).count()
    assert events_count_before == 1

    # Retry the execution
    with patch.object(
        CRMAdapter,
        "execute_action",
        return_value={"lead_id": "retried_999"},
    ):
        retried_exec = retry_execution(db=db_session, execution_id=failed_exec.id, organization_id=org_id)

    assert retried_exec.status == "success"
    # Invariant: A retry must NOT create a new trigger event in WorkflowTriggerEvent
    events_count_after = db_session.query(WorkflowTriggerEvent).filter_by(workflow_id=wf_id).count()
    assert events_count_after == events_count_before
