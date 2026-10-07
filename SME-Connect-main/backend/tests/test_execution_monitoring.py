from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.database.models import Connection, Membership, Organization, User, Workflow, WorkflowExecution, WorkflowStepExecution, WorkflowVersion
from app.database.connection import get_db
from app.main import app


@pytest.fixture
def client(db_session):
    def _get_db():
        yield db_session
    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _setup_org_user(db_session, email="owner@monitor.com"):
    user = User(
        email=email,
        hashed_password="pw",
        full_name="Monitoring Owner",
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name="Monitoring Org")
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


def _create_and_publish_workflow(db_session, user, org, name="Lead Sync Workflow"):
    definition = {
        "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
        "steps": [
            {
                "id": "check-vip",
                "type": "condition",
                "field": "trigger.values.Category",
                "operator": "equals",
                "value": "VIP",
            },
            {
                "id": "create-lead",
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
    }

    wf = Workflow(
        organization_id=org.id,
        created_by=user.id,
        name=name,
        status="published",
    )
    db_session.add(wf)
    db_session.flush()

    now = datetime.now(timezone.utc)
    version = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition=definition,
        created_by=user.id,
        published_at=now,
    )
    db_session.add(version)
    db_session.flush()

    return wf, version


def _add_connections(db_session, org):
    from app.core.security import encrypt_credentials

    sheets_conn = Connection(
        organization_id=org.id,
        connector_slug="google_sheets",
        name="Org Sheets",
        auth_type="api_key",
        config={"spreadsheet_id": "sheet_123"},
        credentials=encrypt_credentials({"client_id": "svc_client", "client_secret": "svc_secret"}),
        status="active",
    )
    crm_conn = Connection(
        organization_id=org.id,
        connector_slug="crm",
        name="Org CRM",
        auth_type="api_key",
        config={"crm_provider": "HubSpot"},
        credentials=encrypt_credentials({"api_key": "crm_key_123"}),
        status="active",
    )
    db_session.add_all([sheets_conn, crm_conn])
    db_session.flush()


def _register_and_login(client, name="Monitor User", email="owner@monitor.com", password="SecurePassword123!"):
    reg_resp = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert reg_resp.status_code == 201, reg_resp.text
    token_verify = reg_resp.json()["verification_token"]
    client.post("/auth/verify-email", json={"token": token_verify})
    login_resp = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_list_executions_with_details_and_filters(client):
    # Setup user and org via API
    headers = _register_and_login(client, name="Tester", email="test_monitor_user@example.com")

    # Create Org
    org_resp = client.post("/organizations", json={"name": "Monitor Corp"}, headers=headers)
    assert org_resp.status_code == 201

    # Connect Google Sheets and CRM
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Sheets",
            "auth_type": "api_key",
            "config": {"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
            "credentials": {"client_id": "svc@proj.iam.gserviceaccount.com", "client_secret": "sec123"},
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
            "credentials": {"api_key": "pat_12345"},
        },
        headers=headers,
    )

    # Create Workflow 1
    wf1_resp = client.post(
        "/workflows",
        json={
            "name": "VIP Sync",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
                "steps": [
                    {
                        "id": "step-1",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "mapping": {"name": "trigger.values.Name"},
                    }
                ],
            },
        },
        headers=headers,
    )
    wf1_id = wf1_resp.json()["id"]
    client.post(f"/workflows/{wf1_id}/publish", headers=headers)

    # Execute Workflow 1 (Success)
    exec1_resp = client.post(
        f"/workflows/{wf1_id}/execute",
        json={"trigger_data": {"values": {"Name": "Virat Kohli"}}},
        headers=headers,
    )
    assert exec1_resp.status_code == 200
    exec1_id = exec1_resp.json()["id"]

    # Execute Workflow 1 with another payload
    exec2_resp = client.post(
        f"/workflows/{wf1_id}/execute",
        json={"trigger_data": {"values": {"Name": "Rohit Sharma"}}},
        headers=headers,
    )
    assert exec2_resp.status_code == 200
    exec2_id = exec2_resp.json()["id"]

    # 1. Test GET /executions (All)
    all_execs_resp = client.get("/executions", headers=headers)
    assert all_execs_resp.status_code == 200
    all_execs = all_execs_resp.json()
    assert len(all_execs) >= 2
    
    # Check enriched summary fields
    first = next(e for e in all_execs if e["id"] == exec1_id)
    assert first["workflow_id"] == wf1_id
    assert first["workflow_name"] == "VIP Sync"
    assert first["version_number"] == 1
    assert first["status"] == "success"
    assert first["step_count"] == 1
    assert first["duration_ms"] is not None
    assert first["duration_ms"] >= 0

    # 2. Test GET /executions?workflow_id={wf1_id}
    filtered_wf = client.get(f"/executions?workflow_id={wf1_id}", headers=headers)
    assert filtered_wf.status_code == 200
    assert all(e["workflow_id"] == wf1_id for e in filtered_wf.json())

    # 3. Test GET /workflows/{wf1_id}/executions
    wf_alias_resp = client.get(f"/workflows/{wf1_id}/executions", headers=headers)
    assert wf_alias_resp.status_code == 200
    assert len(wf_alias_resp.json()) >= 2

    # 4. Test GET /executions?status=success
    success_execs = client.get("/executions?status=success", headers=headers)
    assert success_execs.status_code == 200
    assert all(e["status"] == "success" for e in success_execs.json())

    # 5. Test invalid status filter returns 400
    bad_status = client.get("/executions?status=not_a_valid_status", headers=headers)
    assert bad_status.status_code == 400

    # 6. Test GET /executions/{execution_id} detail view
    detail_resp = client.get(f"/executions/{exec1_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == exec1_id
    assert detail["workflow_name"] == "VIP Sync"
    assert detail["version_number"] == 1
    assert detail["status"] == "success"
    assert detail["duration_ms"] is not None
    assert len(detail["steps"]) == 1
    step = detail["steps"][0]
    assert step["step_id"] == "step-1"
    assert step["step_type"] == "action"
    assert step["connector"] == "crm"
    assert step["action"] == "create_lead"
    assert step["status"] == "success"
    assert step["duration_ms"] is not None
    assert step["input_data"]["name"] == "Virat Kohli"
    assert step["output_data"]["action"] == "create_lead"


def test_execution_monitoring_multi_tenant_isolation(client):
    # Org A User
    h_a = _register_and_login(client, name="User A", email="user_a@tenant.com")
    client.post("/organizations", json={"name": "Org A"}, headers=h_a)

    # Org B User
    h_b = _register_and_login(client, name="User B", email="user_b@tenant.com")
    client.post("/organizations", json={"name": "Org B"}, headers=h_b)

    # Org A Connectors & Workflow
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Sheets A",
            "auth_type": "api_key",
            "config": {"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
            "credentials": {"client_id": "svc@a.iam.gserviceaccount.com", "client_secret": "secA"},
        },
        headers=h_a,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "CRM A",
            "auth_type": "api_key",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_A"},
        },
        headers=h_a,
    )
    wf_a = client.post(
        "/workflows",
        json={
            "name": "Org A Workflow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
                "steps": [
                    {
                        "id": "s1",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "mapping": {"name": "trigger.values.name"},
                    }
                ],
            },
        },
        headers=h_a,
    ).json()["id"]
    client.post(f"/workflows/{wf_a}/publish", headers=h_a)

    # Execute workflow in Org A
    exec_a = client.post(
        f"/workflows/{wf_a}/execute",
        json={"trigger_data": {"values": {"name": "Tenant A Secret Customer"}}},
        headers=h_a,
    ).json()["id"]

    # 1. User B listing executions should NOT see Org A execution
    b_list = client.get("/executions", headers=h_b).json()
    assert all(e["id"] != exec_a for e in b_list)

    # 2. User B requesting Org A execution detail directly should receive 404
    b_detail = client.get(f"/executions/{exec_a}", headers=h_b)
    assert b_detail.status_code == 404


def test_execution_monitoring_scrubs_secrets_in_payloads(client):
    h = _register_and_login(client, name="Scrub User", email="scrub_test@example.com")
    client.post("/organizations", json={"name": "Scrub Org"}, headers=h)

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Sheets",
            "auth_type": "api_key",
            "config": {"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
            "credentials": {"client_id": "svc@iam.gserviceaccount.com", "client_secret": "my_client_secret"},
        },
        headers=h,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "CRM",
            "auth_type": "api_key",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "raw_crm_secret_token"},
        },
        headers=h,
    )

    wf_id = client.post(
        "/workflows",
        json={
            "name": "Scrubbed Workflow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
                "steps": [
                    {
                        "id": "step-scrub",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "mapping": {
                            "name": "trigger.values.Name",
                            "api_key": "trigger.secret_token",
                        },
                    }
                ],
            },
        },
        headers=h,
    ).json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=h)

    # Pass trigger payload with sensitive tokens
    exec_resp = client.post(
        f"/workflows/{wf_id}/execute",
        json={
            "trigger_data": {
                "values": {"Name": "Safe Name"},
                "secret_token": "super_secret_payload_key",
                "api_key": "leaked_api_key_123",
            }
        },
        headers=h,
    )
    assert exec_resp.status_code == 200
    exec_id = exec_resp.json()["id"]

    # Fetch execution detail
    detail = client.get(f"/executions/{exec_id}", headers=h).json()

    # Verify secrets are scrubbed in trigger_data and step input_data
    assert detail["trigger_data"]["secret_token"] == "••••••••"
    assert detail["trigger_data"]["api_key"] == "••••••••"
    assert detail["steps"][0]["input_data"]["api_key"] == "••••••••"
    assert "super_secret_payload_key" not in str(detail)
    assert "leaked_api_key_123" not in str(detail)


def test_get_nonexistent_execution_returns_404(client):
    h = _register_and_login(client, name="Test", email="nonexistent@test.com")
    client.post("/organizations", json={"name": "Org"}, headers=h)

    resp = client.get("/executions/999999", headers=h)
    assert resp.status_code == 404
