from app.modules.executions.service import execute_workflow


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


def setup_monitoring_env(client, email: str = "monitor@test.com", org_name: str = "Monitor Org") -> tuple[dict, int, int]:
    headers = register_and_login(client, "Monitor Admin", email)
    org_id = client.post("/organizations", json={"name": org_name}, headers=headers).json()["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Monitor Sheet",
            "config": {"spreadsheet_id": "sheet_mon_1"},
            "credentials": {"client_id": "svc@g.com", "client_secret": "secret_oauth_token_xyz"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Monitor CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "api_key_secret_123"},
        },
        headers=headers,
    )

    payload = {
        "name": "Customer Sync Flow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_mon_1"},
            },
            "steps": [
                {
                    "id": "check-valid-email",
                    "type": "condition",
                    "field": "trigger.values.Email",
                    "operator": "is_not_empty",
                    "value": None,
                },
                {
                    "id": "create-customer",
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

    return headers, org_id, wf_id


def test_list_executions_endpoint_and_filters(client, db_session):
    headers, org_id, wf_id = setup_monitoring_env(client, "list_filter@test.com", "List Org")

    # 1. Trigger successful execution
    execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"values": {"Name": "Anita Roy", "Email": "anita@enterprise.com"}},
        organization_id=org_id,
    )

    # 2. Trigger execution with condition skipped / different trigger
    execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"values": {"Name": "Bob NoEmail", "Email": ""}},
        organization_id=org_id,
    )

    # GET /executions
    resp = client.get("/executions", headers=headers)
    assert resp.status_code == 200
    executions = resp.json()
    assert len(executions) >= 2

    # Filter by workflow_id
    resp_wf = client.get(f"/executions?workflow_id={wf_id}", headers=headers)
    assert resp_wf.status_code == 200
    assert len(resp_wf.json()) == 2
    for item in resp_wf.json():
        assert item["workflow_id"] == wf_id
        assert item["workflow_name"] == "Customer Sync Flow"

    # Filter by non-existent workflow
    resp_none = client.get("/executions?workflow_id=99999", headers=headers)
    assert resp_none.status_code == 200
    assert len(resp_none.json()) == 0

    # Filter by status
    resp_success = client.get("/executions?status=success", headers=headers)
    assert resp_success.status_code == 200
    assert len(resp_success.json()) == 2

    resp_failed = client.get("/executions?status=failed", headers=headers)
    assert resp_failed.status_code == 200
    assert len(resp_failed.json()) == 0


def test_get_execution_detail_and_steps_timeline(client, db_session):
    headers, org_id, wf_id = setup_monitoring_env(client, "detail_timeline@test.com", "Detail Org")

    # Run execution with email
    exec_record = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"values": {"Name": "Suresh Raina", "Email": "suresh@cricket.in"}},
        organization_id=org_id,
    )

    # GET /executions/{id}
    resp = client.get(f"/executions/{exec_record.id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()

    assert detail["id"] == exec_record.id
    assert detail["workflow_id"] == wf_id
    assert detail["workflow_name"] == "Customer Sync Flow"
    assert detail["status"] == "success"
    assert detail["started_at"] is not None
    assert detail["completed_at"] is not None

    # Step details
    steps = detail["steps"]
    assert len(steps) == 2

    # Step 1: condition
    assert steps[0]["step_id"] == "check-valid-email"
    assert steps[0]["status"] == "success"
    assert steps[0]["output_data"]["condition_met"] is True

    # Step 2: action
    assert steps[1]["step_id"] == "create-customer"
    assert steps[1]["status"] == "success"
    assert steps[1]["input_data"]["name"] == "Suresh Raina"
    assert steps[1]["input_data"]["email"] == "suresh@cricket.in"
    assert steps[1]["output_data"]["success"] is True
    assert steps[1]["output_data"]["lead_id"] is not None


def test_failed_step_diagnostics_and_visibility(client, db_session):
    headers, org_id, wf_id = setup_monitoring_env(client, "failed_diag@test.com", "Diag Org")

    # Trigger with missing required input causing action/mapping failure
    exec_record = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"values": {"WrongField": "Value"}},  # Missing 'Email' which condition checks
        organization_id=org_id,
    )

    # Step 1 evaluates condition is_not_empty on missing field -> False, skips step 2, completes
    resp = client.get(f"/executions/{exec_record.id}", headers=headers)
    detail = resp.json()
    assert detail["status"] == "success"
    assert detail["steps"][1]["status"] == "skipped"
    assert detail["steps"][1]["output_data"]["skipped"] is True


def test_executions_organization_isolation(client, db_session):
    # Org 1
    h1, org1_id, wf1_id = setup_monitoring_env(client, "org1_mon@test.com", "Org 1")
    exec1 = execute_workflow(
        db=db_session,
        workflow_id=wf1_id,
        trigger_data={"values": {"Name": "User 1", "Email": "u1@org1.com"}},
        organization_id=org1_id,
    )

    # Org 2
    h2, org2_id, wf2_id = setup_monitoring_env(client, "org2_mon@test.com", "Org 2")

    # Org 2 listing executions must NOT see Org 1 executions
    resp_org2 = client.get("/executions", headers=h2)
    assert resp_org2.status_code == 200
    ids_in_org2 = [e["id"] for e in resp_org2.json()]
    assert exec1.id not in ids_in_org2

    # Org 2 requesting Org 1's execution detail directly gets 404
    resp_cross = client.get(f"/executions/{exec1.id}", headers=h2)
    assert resp_cross.status_code == 404


def test_executions_never_expose_credentials(client, db_session):
    headers, org_id, wf_id = setup_monitoring_env(client, "creds_leak@test.com", "NoLeak Org")

    exec_record = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"values": {"Name": "Sanitize Test", "Email": "clean@test.com"}},
        organization_id=org_id,
    )

    # Detailed response
    resp = client.get(f"/executions/{exec_record.id}", headers=headers)
    body_text = resp.text

    # Credentials must NEVER be present anywhere in response body
    assert "secret_oauth_token_xyz" not in body_text
    assert "api_key_secret_123" not in body_text


def test_manual_run_and_poll_cycle_endpoints(client):
    headers, org_id, wf_id = setup_monitoring_env(client, "manual_run@test.com", "Manual Org")

    # 1. Manual Run endpoint POST /executions/run/{wf_id}
    run_resp = client.post(
        f"/executions/run/{wf_id}",
        json={"trigger_data": {"values": {"Name": "Manual Run", "Email": "manual@test.com"}}},
        headers=headers,
    )
    assert run_resp.status_code == 200
    data = run_resp.json()
    assert data["workflow_id"] == wf_id
    assert data["status"] == "success"
    assert data["steps"][1]["input_data"]["name"] == "Manual Run"

    # 2. Trigger Poll Cycle endpoint POST /executions/poll-cycle
    cycle_resp = client.post("/executions/poll-cycle", headers=headers)
    assert cycle_resp.status_code == 200
    cycle_data = cycle_resp.json()
    assert cycle_data["workflows_polled"] >= 1
    assert "executions_created" in cycle_data
