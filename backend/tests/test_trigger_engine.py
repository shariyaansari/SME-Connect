from sqlalchemy import select
from app.database.models import WorkflowTriggerState
from app.modules.executions.runner import poll_workflow_trigger, run_trigger_poll_cycle
from app.modules.executions.service import to_detail_response


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


def setup_org_and_connections(client, email: str = "admin@trigger.com", org_name: str = "Trigger Org") -> tuple[dict, int]:
    headers = register_and_login(client, "Trigger Admin", email)
    org_id = client.post("/organizations", json={"name": org_name}, headers=headers).json()["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Live Sheets",
            "config": {"spreadsheet_id": "sheet_trigger_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_trig_123"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Live CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_key_live_789"},
        },
        headers=headers,
    )
    return headers, org_id


def create_sample_published_workflow(client, headers: dict) -> int:
    payload = {
        "name": "Automated Lead Intake",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_trigger_123"},
            },
            "steps": [
                {
                    "id": "validate-email",
                    "type": "condition",
                    "field": "trigger.values.Email",
                    "operator": "is_not_empty",
                    "value": None,
                },
                {
                    "id": "push-to-crm",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {
                        "name": "trigger.values.Name",
                        "email": "trigger.values.Email",
                    },
                },
            ],
        },
    }
    wf_id = client.post("/workflows", json=payload, headers=headers).json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=headers)
    return wf_id


# ============================================================================
# Module 4 Tests: Trigger Polling, Cursor Advancement, and Poll Cycle
# ============================================================================

def test_trigger_polling_and_cursor_advancement(client, db_session):
    headers, org_id = setup_org_and_connections(client, "poll_adv@test.com", "Advance Org")
    wf_id = create_sample_published_workflow(client, headers)

    # Poll Cycle 1: First poll should detect row 2
    executions_cycle_1 = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)
    assert len(executions_cycle_1) == 1
    exec1 = executions_cycle_1[0]
    assert exec1.status == "success"
    assert exec1.trigger_data["row_index"] == 2

    # Check that cursor was recorded and advanced
    trigger_state = db_session.scalar(
        select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == wf_id)
    )
    assert trigger_state is not None
    assert trigger_state.cursor == {"last_row_index": 2} or trigger_state.cursor == 2
    assert trigger_state.last_polled_at is not None

    # Poll Cycle 2: Next poll reads next row (row 3)
    executions_cycle_2 = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)
    assert len(executions_cycle_2) == 1
    exec2 = executions_cycle_2[0]
    assert exec2.status == "success"
    assert exec2.trigger_data["row_index"] == 3

    # Cursor must be advanced to row 3
    db_session.refresh(trigger_state)
    assert trigger_state.cursor == {"last_row_index": 3} or trigger_state.cursor == 3


def test_poll_cycle_excludes_draft_and_paused_workflows(client, db_session):
    headers, org_id = setup_org_and_connections(client, "cycle_filter@test.com", "Filter Org")

    # 1. Published workflow
    pub_wf_id = create_sample_published_workflow(client, headers)

    # 2. Draft workflow
    draft_payload = {
        "name": "Draft Workflow",
        "definition": {
            "trigger": {"connector": "google_sheets", "event": "new_row"},
            "steps": [{"id": "s1", "type": "action", "connector": "crm", "action": "create_lead", "mapping": {"name": "trigger.name"}}],
        },
    }
    client.post("/workflows", json=draft_payload, headers=headers).json()["id"]

    # 3. Paused workflow
    paused_payload = {
        "name": "Paused Workflow",
        "definition": {
            "trigger": {"connector": "google_sheets", "event": "new_row"},
            "steps": [{"id": "s2", "type": "action", "connector": "crm", "action": "create_lead", "mapping": {"name": "trigger.name"}}],
        },
    }
    paused_wf_id = client.post("/workflows", json=paused_payload, headers=headers).json()["id"]
    client.post(f"/workflows/{paused_wf_id}/publish", headers=headers)
    client.post(f"/workflows/{paused_wf_id}/pause", headers=headers)

    # Run complete poll cycle for this organization
    cycle_result = run_trigger_poll_cycle(db=db_session, organization_id=org_id)

    # Only 1 workflow (the published one) must be polled
    assert cycle_result["workflows_polled"] == 1
    assert cycle_result["events_detected"] == 1
    assert cycle_result["executions_created"] == 1
    assert len(cycle_result["errors"]) == 0


def test_trigger_polling_missing_connection(client, db_session):
    headers = register_and_login(client, "Missing Conn", "missing_conn@test.com")
    org_id = client.post("/organizations", json={"name": "Missing Org"}, headers=headers).json()["id"]

    # Connect Google Sheets but NOT CRM
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Solo Sheets",
            "config": {"spreadsheet_id": "solo_sheet"},
            "credentials": {"client_id": "svc@g.com", "client_secret": "sec_123"},
        },
        headers=headers,
    )

    # Connect CRM temporarily to allow publishing, then delete connection
    crm_id = client.post(
        "/connectors",
        json={"connector_slug": "crm", "name": "Temp CRM", "config": {"crm_provider": "HubSpot"}, "credentials": {"api_key": "k"}},
        headers=headers,
    ).json()["id"]

    wf_id = client.post(
        "/workflows",
        json={
            "name": "Disconnect Test",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [{"id": "s1", "type": "action", "connector": "crm", "action": "create_lead", "mapping": {"name": "trigger.values.Name"}}],
            },
        },
        headers=headers,
    ).json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Delete CRM connection
    client.delete(f"/connectors/{crm_id}", headers=headers)

    # Polling should execute the trigger, but when action executes without CRM, execution fails gracefully
    execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)
    assert len(execs) == 1
    assert execs[0].status == "failed"
    assert "crm" in execs[0].error_message.lower()


def test_multi_step_workflow_trigger_and_chaining(client, db_session):
    headers, org_id = setup_org_and_connections(client, "chain@test.com", "Chain Org")

    # Add custom API connector for step 3
    client.post(
        "/connectors",
        json={
            "connector_slug": "custom_api",
            "name": "Internal Webhook",
            "config": {"base_url": "https://api.internal.com"},
            "credentials": {"api_key": "wh_sec_999"},
        },
        headers=headers,
    )

    payload = {
        "name": "Three Step Pipeline",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
            },
            "steps": [
                {
                    "id": "step-1-cond",
                    "type": "condition",
                    "field": "trigger.values.Name",
                    "operator": "is_not_empty",
                    "value": None,
                },
                {
                    "id": "step-2-crm",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "mapping": {
                        "name": "trigger.values.Name",
                        "email": "trigger.values.Email",
                    },
                },
                {
                    "id": "step-3-notify",
                    "type": "action",
                    "connector": "custom_api",
                    "action": "http_request",
                    "config": {"endpoint": "/leads/notify", "method": "POST"},
                    "mapping": {
                        "crm_lead_id": "steps.step-2-crm.lead_id",
                        "customer_name": "trigger.values.Name",
                    },
                },
            ],
        },
    }
    wf_id = client.post("/workflows", json=payload, headers=headers).json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)
    assert len(execs) == 1
    execution = execs[0]
    assert execution.status == "success"

    steps = sorted(execution.step_executions, key=lambda s: s.step_index)
    assert len(steps) == 3
    assert steps[0].step_id == "step-1-cond"
    assert steps[0].status == "success"

    assert steps[1].step_id == "step-2-crm"
    assert steps[1].status == "success"
    crm_lead_id = steps[1].output_data["lead_id"]

    assert steps[2].step_id == "step-3-notify"
    assert steps[2].status == "success"
    assert steps[2].input_data["crm_lead_id"] == crm_lead_id


def test_trigger_execution_no_credential_leakage(client, db_session):
    headers, org_id = setup_org_and_connections(client, "leak_test@test.com", "Leak Org")
    wf_id = create_sample_published_workflow(client, headers)

    execs = poll_workflow_trigger(db=db_session, workflow_id=wf_id, organization_id=org_id)
    assert len(execs) == 1
    execution = execs[0]

    # Convert to response
    detail = to_detail_response(execution)
    dump_json = detail.model_dump_json()

    # Secret credentials must NEVER be in execution payloads
    assert "sec_trig_123" not in dump_json
    assert "pat_key_live_789" not in dump_json


def test_trigger_polling_organization_isolation(client, db_session):
    # Org 1
    h1, org1_id = setup_org_and_connections(client, "org1_trig@test.com", "Org 1")
    wf1_id = create_sample_published_workflow(client, h1)

    # Org 2
    h2, org2_id = setup_org_and_connections(client, "org2_trig@test.com", "Org 2")
    wf2_id = create_sample_published_workflow(client, h2)

    # Polling Org 1 exclusively should only poll Org 1's workflow
    cycle1 = run_trigger_poll_cycle(db=db_session, organization_id=org1_id)
    assert cycle1["workflows_polled"] == 1
    assert cycle1["executions_created"] == 1

    # Org 1 cannot poll Org 2's workflow
    import pytest
    with pytest.raises(ValueError, match="Workflow not found"):
        poll_workflow_trigger(db=db_session, workflow_id=wf2_id, organization_id=org1_id)
