import pytest
from datetime import datetime, timezone
from sqlalchemy import select

from app.core.security import encrypt_credentials
from app.database.models import (
    Connection,
    Membership,
    Organization,
    User,
    Workflow,
    WorkflowExecution,
    WorkflowTriggerState,
    WorkflowVersion,
)
from app.modules.workflows.trigger_service import (
    get_or_create_trigger_state,
    poll_workflow_trigger,
    run_trigger_poll_cycle,
)


def _setup_org_user(db_session, user_name="Trigger User", email="trigger@sme.com", org_name="Trigger Org"):
    user = User(
        name=user_name,
        email=email,
        password_hash="hashed_pw",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name=org_name)
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


def _create_published_workflow(db_session, user, org, definition=None):
    now = datetime.now(timezone.utc)
    if definition is None:
        definition = {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
            },
            "steps": [
                {
                    "id": "step-lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {"crm_provider": "HubSpot"},
                    "mapping": {
                        "name": "trigger.values.Name",
                        "email": "trigger.values.Email",
                        "phone": "trigger.values.Phone",
                    },
                }
            ],
        }

    wf = Workflow(
        organization_id=org.id,
        name="Lead Auto Ingestion",
        status="published",
        created_by=user.id,
    )
    db_session.add(wf)
    db_session.flush()

    version = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition=definition,
        created_by=user.id,
        published_at=now,
    )
    db_session.add(version)
    db_session.commit()
    db_session.refresh(wf)
    db_session.refresh(version)
    return wf, version


def _add_connections(db_session, org):
    sheets_conn = Connection(
        organization_id=org.id,
        connector_slug="google_sheets",
        name="Main Google Sheet",
        auth_type="api_key",
        config={"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
        credentials=encrypt_credentials({
            "client_id": "svc@project.iam.gserviceaccount.com",
            "client_secret": "valid_secret_key",
        }),
        status="active",
    )
    crm_conn = Connection(
        organization_id=org.id,
        connector_slug="crm",
        name="HubSpot",
        auth_type="api_key",
        config={"crm_provider": "HubSpot"},
        credentials=encrypt_credentials({"api_key": "pat-12345"}),
        status="active",
    )
    db_session.add_all([sheets_conn, crm_conn])
    db_session.commit()
    return sheets_conn, crm_conn


def test_trigger_polling_and_cursor_advancement(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, version = _create_published_workflow(db_session, user, org)
    _add_connections(db_session, org)

    # Initial poll
    result1 = poll_workflow_trigger(db_session, wf)

    assert result1["status"] == "success"
    assert result1["records_count"] >= 1
    assert len(result1["execution_ids"]) == 1
    new_cursor = result1["new_cursor"]
    assert new_cursor is not None

    # Verify persistent WorkflowTriggerState
    state = db_session.scalar(
        select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == wf.id)
    )
    assert state is not None
    assert state.cursor == new_cursor
    assert state.last_polled_at is not None

    # Verify execution record created by the poll
    execution = db_session.get(WorkflowExecution, result1["execution_ids"][0])
    assert execution is not None
    assert execution.status == "success"
    assert execution.trigger_data["values"]["Name"] == "Rahul Verma"

    # Second poll: cursor should advance further
    result2 = poll_workflow_trigger(db_session, wf)
    assert result2["status"] == "success"
    db_session.refresh(state)
    assert state.cursor["last_row_index"] > new_cursor["last_row_index"]


def test_cursor_does_not_advance_if_execution_fails(db_session):
    user, org, _ = _setup_org_user(db_session)
    # Workflow references action with a broken mapping path that will fail
    broken_def = {
        "trigger": {"connector": "google_sheets", "event": "new_row"},
        "steps": [
            {
                "id": "step-fail",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "name": "trigger.values.NonExistentField",
                },
            }
        ],
    }
    wf, _ = _create_published_workflow(db_session, user, org, definition=broken_def)
    _add_connections(db_session, org)

    state = get_or_create_trigger_state(db_session, wf, 1)
    state.cursor = {"last_row_index": 10}
    db_session.commit()

    # Poll workflow: execution will fail due to mapping error
    result = poll_workflow_trigger(db_session, wf)
    assert result["status"] == "success"  # poll ran, but execution inside failed

    # Verify cursor was NOT advanced because executions failed
    db_session.refresh(state)
    assert state.cursor == {"last_row_index": 10}


def test_paused_and_draft_workflows_are_excluded_from_poll(db_session):
    user, org, _ = _setup_org_user(db_session)
    _add_connections(db_session, org)

    # 1. Draft workflow
    wf_draft, _ = _create_published_workflow(db_session, user, org)
    wf_draft.status = "draft"

    # 2. Paused workflow
    wf_paused, _ = _create_published_workflow(db_session, user, org)
    wf_paused.status = "paused"

    # 3. Active published workflow
    wf_active, _ = _create_published_workflow(db_session, user, org)
    wf_active.status = "published"

    db_session.commit()

    # Run poll cycle across organization
    results = run_trigger_poll_cycle(db_session, organization_id=org.id)

    # Only wf_active should be polled
    polled_wf_ids = [r["workflow_id"] for r in results]
    assert wf_active.id in polled_wf_ids
    assert wf_draft.id not in polled_wf_ids
    assert wf_paused.id not in polled_wf_ids


def test_missing_trigger_connection_gracefully_skipped(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, _ = _create_published_workflow(db_session, user, org)
    # Do NOT add connections

    result = poll_workflow_trigger(db_session, wf)
    assert result["status"] == "skipped"
    assert "No active connection" in result["reason"]


def test_trigger_polling_with_condition_branching(db_session):
    user, org, _ = _setup_org_user(db_session)
    _add_connections(db_session, org)

    # Workflow where condition checks if Name equals "Rahul Verma"
    cond_def = {
        "trigger": {"connector": "google_sheets", "event": "new_row"},
        "steps": [
            {
                "id": "verify-name",
                "type": "condition",
                "field": "trigger.values.Name",
                "operator": "equals",
                "value": "Rahul Verma",
            },
            {
                "id": "crm-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "name": "trigger.values.Name",
                    "email": "trigger.values.Email",
                    "phone": "trigger.values.Phone",
                },
            },
        ],
    }
    wf, _ = _create_published_workflow(db_session, user, org, definition=cond_def)

    result = poll_workflow_trigger(db_session, wf)
    assert result["status"] == "success"
    assert len(result["execution_ids"]) == 1

    exec_record = db_session.get(WorkflowExecution, result["execution_ids"][0])
    assert exec_record.status == "success"
    assert len(exec_record.step_executions) == 2
    assert exec_record.step_executions[0].output_data["condition_met"] is True
    assert exec_record.step_executions[1].status == "success"


def test_multi_tenant_trigger_isolation(db_session):
    # Org 1
    user1, org1, _ = _setup_org_user(db_session, "User 1", "u1@org1.com", "Org 1")
    wf1, _ = _create_published_workflow(db_session, user1, org1)
    _add_connections(db_session, org1)

    # Org 2
    user2, org2, _ = _setup_org_user(db_session, "User 2", "u2@org2.com", "Org 2")
    wf2, _ = _create_published_workflow(db_session, user2, org2)
    _add_connections(db_session, org2)

    # Poll cycle for Org 1 only
    results_org1 = run_trigger_poll_cycle(db_session, organization_id=org1.id)
    org1_ids = [r["workflow_id"] for r in results_org1]
    assert wf1.id in org1_ids
    assert wf2.id not in org1_ids

    # Verify trigger state isolation
    state1 = db_session.scalar(select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == wf1.id))
    state2 = db_session.scalar(select(WorkflowTriggerState).where(WorkflowTriggerState.workflow_id == wf2.id))
    assert state1.organization_id == org1.id
    assert state2 is None  # Org 2 was not polled


def test_poll_cycle_api_endpoints(client, db_session):
    # Setup user and org via API
    register_payload = {
        "name": "Trigger API User",
        "email": "trigapi@sme.com",
        "password": "SecurePassword123!",
    }
    reg_resp = client.post("/auth/register", json=register_payload)
    client.post("/auth/verify-email", json={"token": reg_resp.json()["verification_token"]})
    login_resp = client.post(
        "/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    client.post("/organizations", json={"name": "Polling Org"}, headers=headers)

    # Add connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Sheets",
            "auth_type": "api_key",
            "config": {"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
            "credentials": {
                "client_id": "svc@project.iam.gserviceaccount.com",
                "client_secret": "valid_secret_key",
            },
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "CRM",
            "auth_type": "api_key",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat-12345"},
        },
        headers=headers,
    )

    # Create & publish workflow
    wf_create = client.post(
        "/workflows",
        json={
            "name": "Sheets to CRM Polled Flow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
                "steps": [
                    {
                        "id": "step-crm",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "mapping": {
                            "name": "trigger.values.Name",
                            "email": "trigger.values.Email",
                            "phone": "trigger.values.Phone",
                        },
                    }
                ],
            },
        },
        headers=headers,
    )
    wf_id = wf_create.json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # 1. Test POST /workflows/{id}/poll
    poll_single_resp = client.post(f"/workflows/{wf_id}/poll", headers=headers)
    assert poll_single_resp.status_code == 200
    single_data = poll_single_resp.json()
    assert single_data["status"] == "success"
    assert single_data["records_count"] >= 1

    # 2. Test POST /workflows/triggers/poll (cycle)
    cycle_resp = client.post("/workflows/triggers/poll", headers=headers)
    assert cycle_resp.status_code == 200
    cycle_data = cycle_resp.json()
    assert isinstance(cycle_data, list)
    assert len(cycle_data) >= 1
    assert cycle_data[0]["workflow_id"] == wf_id
