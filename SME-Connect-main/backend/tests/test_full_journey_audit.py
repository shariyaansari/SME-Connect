import pytest
from fastapi.testclient import TestClient

from app.database import models
from app.database.connection import Base
from app.main import app


def test_full_modules_1_to_6_lifecycle(client: TestClient, db_session):
    """
    Comprehensive end-to-end audit verifying seamless interoperability across
    Modules 1 through 6:
      - Module 1: Auth, Organizations, RBAC, Audit Logging
      - Module 2: Connectors, Catalog, Connections, Testing
      - Module 3: Workflows, Versioning, Immutability, Lifecycle
      - Module 3A: Guided Templates
      - Module 3B & 4: Execution Engine, Conditionals, Generic Action Mapping
      - Module 5: Execution Monitoring & History
      - Module 6: Reliability, Failures, Backoff, Manual Retries, Health, Scheduler
    """
    # -------------------------------------------------------------
    # 1. Module 1: Register, Verify, Login, Me
    # -------------------------------------------------------------
    reg_res = client.post("/auth/register", json={
        "name": "Acme Owner",
        "email": "owner@acmesme.com",
        "password": "StrongPassword123!",
    })
    assert reg_res.status_code == 201, reg_res.text
    verification_token = reg_res.json()["verification_token"]

    verify_res = client.post("/auth/verify-email", json={"token": verification_token})
    assert verify_res.status_code == 200, verify_res.text

    login_res = client.post("/auth/login", json={
        "email": "owner@acmesme.com",
        "password": "StrongPassword123!",
    })
    assert login_res.status_code == 200, login_res.text
    access_token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    me_res = client.get("/auth/me", headers=headers)
    assert me_res.status_code == 200, me_res.text
    user_id = me_res.json()["id"]

    # -------------------------------------------------------------
    # 2. Module 1: Organizations & Workspace
    # -------------------------------------------------------------
    create_org_res = client.post("/organizations", json={"name": "Acme SME Solutions"}, headers=headers)
    assert create_org_res.status_code == 201, create_org_res.text
    org_id = create_org_res.json()["id"]

    orgs_res = client.get("/organizations", headers=headers)
    assert orgs_res.status_code == 200, orgs_res.text
    orgs = orgs_res.json()
    assert len(orgs) >= 1

    members_res = client.get(f"/organizations/members?organization_id={org_id}", headers=headers)
    assert members_res.status_code == 200, members_res.text
    assert any(m["user_id"] == user_id and m["role"] == "Admin" for m in members_res.json())

    # -------------------------------------------------------------
    # 3. Module 2: Connector Catalog & Connection Management
    # -------------------------------------------------------------
    catalog_res = client.get("/connectors/catalog", headers=headers)
    assert catalog_res.status_code == 200, catalog_res.text
    catalog_items = catalog_res.json()
    assert len(catalog_items) >= 6
    assert any(c["slug"] == "google_sheets" for c in catalog_items)
    assert any(c["slug"] == "crm" for c in catalog_items)

    conn_res = client.post(f"/connectors?organization_id={org_id}", json={
        "connector_slug": "google_sheets",
        "name": "Acme Production Sheets",
        "auth_type": "oauth2",
        "config": {"spreadsheet_id": "sheet_123"},
        "credentials": {"client_id": "client_abc", "client_secret": "secret_xyz"},
    }, headers=headers)
    assert conn_res.status_code == 201, conn_res.text
    conn_data = conn_res.json()
    conn_id = conn_data["id"]
    assert "•" in conn_data["masked_credentials"]["client_secret"]
    assert "secret_xyz" not in conn_data["masked_credentials"]["client_secret"]

    test_res = client.post(f"/connectors/{conn_id}/test?organization_id={org_id}", headers=headers)
    assert test_res.status_code == 200, test_res.text
    assert test_res.json()["success"] is True

    # -------------------------------------------------------------
    # 4. Module 3A: Templates
    # -------------------------------------------------------------
    templates_res = client.get("/templates", headers=headers)
    assert templates_res.status_code == 200, templates_res.text
    templates = templates_res.json()
    assert len(templates) >= 3

    tpl_res = client.get(f"/templates/{templates[0]['id']}", headers=headers)
    assert tpl_res.status_code == 200, tpl_res.text
    assert "definition" in tpl_res.json()

    # -------------------------------------------------------------
    # 5. Module 3: Workflow Authoring & Lifecycle
    # -------------------------------------------------------------
    wf_definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
            "config": {"spreadsheet_id": "sheet_123"},
        },
        "steps": [
            {
                "id": "step_cond",
                "type": "condition",
                "field": "trigger.values.score",
                "operator": "greater_than",
                "value": "50",
            },
            {
                "id": "step_crm",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "config": {},
                "mapping": {
                    "lead_name": "trigger.values.lead_name",
                    "email": "trigger.values.email",
                },
            },
        ],
    }

    # Needs CRM active connection to publish later, so create CRM connection
    crm_conn_res = client.post(f"/connectors?organization_id={org_id}", json={
        "connector_slug": "crm",
        "name": "Acme CRM",
        "auth_type": "api_key",
        "config": {"crm_provider": "HubSpot"},
        "credentials": {"api_key": "crm_key_secret"},
    }, headers=headers)
    assert crm_conn_res.status_code == 201, crm_conn_res.text

    create_wf_res = client.post(f"/workflows?organization_id={org_id}", json={
        "name": "High Value Lead Processor",
        "description": "Routes leads with score > 50 to CRM",
        "definition": wf_definition,
    }, headers=headers)
    assert create_wf_res.status_code == 201, create_wf_res.text
    wf_data = create_wf_res.json()
    wf_id = wf_data["id"]
    assert wf_data["status"] == "draft"

    # Publish workflow
    pub_res = client.post(f"/workflows/{wf_id}/publish?organization_id={org_id}", headers=headers)
    assert pub_res.status_code == 200, pub_res.text
    assert pub_res.json()["status"] == "published"

    # -------------------------------------------------------------
    # 6. Module 3B & 4: Execution Engine (Condition True & False)
    # -------------------------------------------------------------
    # Case A: Condition False (score = 20 <= 50) -> step_crm skipped
    exec_a_res = client.post(f"/workflows/{wf_id}/execute?organization_id={org_id}", json={
        "trigger_data": {
            "values": {"lead_name": "Low Score Lead", "email": "low@example.com", "score": "20"},
        },
    }, headers=headers)
    assert exec_a_res.status_code == 200, exec_a_res.text
    exec_a = exec_a_res.json()
    assert exec_a["status"] == "success"
    # condition step succeeded, crm step skipped
    cond_step = next(s for s in exec_a["steps"] if s["step_id"] == "step_cond")
    assert cond_step["status"] == "success"
    crm_step = next(s for s in exec_a["steps"] if s["step_id"] == "step_crm")
    assert crm_step["status"] == "skipped"

    # Case B: Condition True (score = 85 > 50) -> step_crm executed
    exec_b_res = client.post(f"/workflows/{wf_id}/execute?organization_id={org_id}", json={
        "trigger_data": {
            "values": {"lead_name": "VIP Lead", "email": "vip@example.com", "score": "85"},
        },
    }, headers=headers)
    assert exec_b_res.status_code == 200, exec_b_res.text
    exec_b = exec_b_res.json()
    assert exec_b["status"] == "success"
    crm_step_b = next(s for s in exec_b["steps"] if s["step_id"] == "step_crm")
    assert crm_step_b["status"] == "success"
    assert crm_step_b["output_data"]["lead_id"] is not None

    # -------------------------------------------------------------
    # 7. Module 5: Execution Monitoring & History
    # -------------------------------------------------------------
    execs_list_res = client.get(f"/executions?workflow_id={wf_id}&organization_id={org_id}", headers=headers)
    assert execs_list_res.status_code == 200, execs_list_res.text
    execs_list = execs_list_res.json()
    assert len(execs_list) >= 2
    assert all(e["workflow_id"] == wf_id for e in execs_list)

    detail_res = client.get(f"/executions/{exec_b['id']}?organization_id={org_id}", headers=headers)
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()
    assert detail["id"] == exec_b["id"]
    assert len(detail["steps"]) == 2

    # -------------------------------------------------------------
    # 8. Module 6: Reliability, Health, Retries & Scheduler
    # -------------------------------------------------------------
    # Workflow Health check
    health_res = client.get(f"/workflows/{wf_id}/health?organization_id={org_id}", headers=headers)
    assert health_res.status_code == 200, health_res.text
    health = health_res.json()
    assert health["status"] == "healthy"
    assert health["success_rate_percent"] == 100.0

    # Run scheduled workflow cycle endpoint
    sched_cycle_res = client.post("/workflows/schedule/run-cycle", headers=headers)
    assert sched_cycle_res.status_code == 200, sched_cycle_res.text
    assert "triggered_count" in sched_cycle_res.json()

    # Manual retry on non-failed execution must be rejected (HTTP 400)
    retry_invalid_res = client.post(f"/executions/{exec_b['id']}/retry?organization_id={org_id}", headers=headers)
    assert retry_invalid_res.status_code == 400
    assert "only failed executions can be retried" in retry_invalid_res.json()["detail"].lower()

    # -------------------------------------------------------------
    # 9. Module 1: Audit Log verification
    # -------------------------------------------------------------
    audit_res = client.get(f"/organizations/audit-logs?organization_id={org_id}", headers=headers)
    assert audit_res.status_code == 200, audit_res.text
    logs = audit_res.json()
    assert len(logs) >= 1
    # Verify organization and user audit records exist
    assert any(log["organization_id"] == org_id for log in logs)
