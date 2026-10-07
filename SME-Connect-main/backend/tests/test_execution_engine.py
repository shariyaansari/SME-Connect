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
    WorkflowStepExecution,
    WorkflowVersion,
)
from app.modules.workflows.execution_service import (
    execute_workflow,
    get_execution,
    list_executions,
)


def _setup_org_user(db_session, user_name="Executor", email="exec@sme.com", org_name="Execution Org"):
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
                "config": {"spreadsheet_id": "sheet_123"},
            },
            "steps": [
                {
                    "id": "create-lead",
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
        name="Lead Creation Automation",
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


def _add_active_connections(db_session, org):
    # Google Sheets connection
    sheets_conn = Connection(
        organization_id=org.id,
        connector_slug="google_sheets",
        name="Google Sheets Main",
        auth_type="api_key",
        config={"spreadsheet_id": "sheet_123"},
        credentials=encrypt_credentials({"api_key": "valid_sheets_key"}),
        status="active",
    )
    # CRM connection
    crm_conn = Connection(
        organization_id=org.id,
        connector_slug="crm",
        name="HubSpot CRM Connection",
        auth_type="api_key",
        config={"crm_provider": "HubSpot"},
        credentials=encrypt_credentials({"api_key": "valid_crm_pat_token"}),
        status="active",
    )
    db_session.add_all([sheets_conn, crm_conn])
    db_session.commit()
    return sheets_conn, crm_conn


def test_execute_published_workflow_success(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, version = _create_published_workflow(db_session, user, org)
    _add_active_connections(db_session, org)

    trigger_data = {
        "row_index": 5,
        "values": {
            "Name": "Aarav Sharma",
            "Email": "aarav@techventures.in",
            "Phone": "+91-9988776655",
        },
    }

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data=trigger_data,
        user_id=user.id,
    )

    assert execution.id is not None
    assert execution.status == "success"
    assert execution.workflow_id == wf.id
    assert execution.workflow_version_id == version.id
    assert execution.organization_id == org.id
    assert execution.completed_at is not None
    assert execution.error_message is None

    # Verify step executions
    assert len(execution.step_executions) == 1
    step_exec = execution.step_executions[0]
    assert step_exec.step_id == "create-lead"
    assert step_exec.status == "success"
    assert step_exec.input_data["name"] == "Aarav Sharma"
    assert step_exec.input_data["email"] == "aarav@techventures.in"
    assert step_exec.output_data["action"] == "create_lead"
    assert "lead_id" in step_exec.output_data


def test_reject_draft_workflow_execution(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, _ = _create_published_workflow(db_session, user, org)
    # Put workflow in draft status
    wf.status = "draft"
    db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        execute_workflow(
            db=db_session,
            workflow_id=wf.id,
            trigger_data={"event": "test"},
            user_id=user.id,
        )

    assert "Cannot execute workflow with status 'draft'" in str(exc_info.value)


def test_reject_paused_workflow_execution(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, _ = _create_published_workflow(db_session, user, org)
    wf.status = "paused"
    db_session.commit()

    with pytest.raises(ValueError) as exc_info:
        execute_workflow(
            db=db_session,
            workflow_id=wf.id,
            trigger_data={"event": "test"},
            user_id=user.id,
        )

    assert "Cannot execute workflow with status 'paused'" in str(exc_info.value)


def test_condition_step_skips_subsequent_actions_when_false(db_session):
    user, org, _ = _setup_org_user(db_session)
    _add_active_connections(db_session, org)

    # Workflow with condition: only create lead if status is "VIP"
    definition = {
        "trigger": {"connector": "google_sheets", "event": "new_row"},
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
                "mapping": {
                    "name": "trigger.values.Name",
                    "email": "trigger.values.Email",
                },
            },
        ],
    }
    wf, _ = _create_published_workflow(db_session, user, org, definition=definition)

    # Case 1: Category is "Standard" (False) -> step 2 is skipped
    execution_false = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={
            "values": {
                "Category": "Standard",
                "Name": "Bob",
                "Email": "bob@gmail.com",
            }
        },
        user_id=user.id,
    )

    assert execution_false.status == "success"
    assert len(execution_false.step_executions) == 2
    assert execution_false.step_executions[0].step_id == "check-vip"
    assert execution_false.step_executions[0].status == "success"
    assert execution_false.step_executions[0].output_data == {"condition_met": False}
    # Second step marked skipped
    assert execution_false.step_executions[1].step_id == "create-lead"
    assert execution_false.step_executions[1].status == "skipped"

    # Case 2: Category is "VIP" (True) -> step 2 is executed
    execution_true = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={
            "values": {
                "Category": "VIP",
                "Name": "Alice VIP",
                "Email": "alice@vip.com",
            }
        },
        user_id=user.id,
    )
    assert execution_true.status == "success"
    assert len(execution_true.step_executions) == 2
    assert execution_true.step_executions[0].output_data == {"condition_met": True}
    assert execution_true.step_executions[1].status == "success"
    assert execution_true.step_executions[1].output_data["action"] == "create_lead"


def test_missing_connector_connection_fails_step_and_execution(db_session):
    user, org, _ = _setup_org_user(db_session)
    # Workflow references CRM, but we DO NOT add a CRM connection to this org
    wf, _ = _create_published_workflow(db_session, user, org)

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"values": {"Name": "Test", "Email": "test@test.com", "Phone": "9988776655"}},
        user_id=user.id,
    )

    assert execution.status == "failed"
    assert "No active connection found for connector 'crm'" in execution.error_message
    assert len(execution.step_executions) == 1
    assert execution.step_executions[0].status == "failed"
    assert "No active connection found" in execution.step_executions[0].error_message


def test_credential_non_exposure_in_execution_and_step_records(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, _ = _create_published_workflow(db_session, user, org)
    _add_active_connections(db_session, org)

    # Pass payload that contains accidental or sensitive field names
    trigger_data = {
        "values": {"Name": "Safe Name", "Email": "safe@email.com"},
        "client_secret": "sensitive_unencrypted_secret_12345",
        "api_key": "sensitive_api_token_54321",
    }

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data=trigger_data,
        user_id=user.id,
    )

    # Verify secrets in trigger_data were sanitized
    assert execution.trigger_data["client_secret"] == "••••••••"
    assert execution.trigger_data["api_key"] == "••••••••"
    assert "sensitive_unencrypted_secret" not in str(execution.trigger_data)


def test_organization_isolation_in_execution(db_session):
    # Org 1
    user1, org1, _ = _setup_org_user(db_session, "User 1", "user1@org1.com", "Org 1")
    wf1, _ = _create_published_workflow(db_session, user1, org1)
    _add_active_connections(db_session, org1)

    # Org 2
    user2, org2, _ = _setup_org_user(db_session, "User 2", "user2@org2.com", "Org 2")

    # User 2 cannot execute User 1's workflow
    with pytest.raises(ValueError) as exc_info:
        execute_workflow(
            db=db_session,
            workflow_id=wf1.id,
            trigger_data={"values": {"Name": "X"}},
            user_id=user2.id,
        )

    assert "not belong to the specified organization" in str(exc_info.value) or "Workflow not found" in str(exc_info.value)


def test_immutable_published_version_execution_reference(db_session):
    user, org, _ = _setup_org_user(db_session)
    wf, v1 = _create_published_workflow(db_session, user, org)
    _add_active_connections(db_session, org)

    # Spawn a new draft version (v2) on the workflow
    v2 = WorkflowVersion(
        workflow_id=wf.id,
        version_number=2,
        definition={"trigger": {"connector": "google_sheets", "event": "new_row"}, "steps": []},
        created_by=user.id,
        published_at=None,  # Unreleased draft
    )
    db_session.add(v2)
    # The workflow published version remains v1
    db_session.commit()

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf.id,
        trigger_data={"values": {"Name": "Immutable Test", "Email": "imm@corp.com", "Phone": "9988776655"}},
        user_id=user.id,
    )

    # Execution must reference the exact published version (v1), NOT the draft v2
    assert execution.workflow_version_id == v1.id
    assert execution.status == "success"


def test_execution_api_endpoint(client, db_session):
    # Setup test using API client
    register_payload = {
        "name": "API Runner",
        "email": "apirunner@sme.com",
        "password": "SecurePassword123!",
    }
    reg_resp = client.post("/auth/register", json=register_payload)
    client.post("/auth/verify-email", json={"token": reg_resp.json()["verification_token"]})
    login_resp = client.post(
        "/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create Org
    org_resp = client.post("/organizations", json={"name": "API Org"}, headers=headers)
    org_id = org_resp.json()["id"]

    # Connect Google Sheets and CRM with valid test credentials
    sheets_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Sheets",
            "auth_type": "api_key",
            "config": {"spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"},
            "credentials": {
                "client_id": "svc@project.iam.gserviceaccount.com",
                "client_secret": "valid_google_cloud_secret",
            },
        },
        headers=headers,
    )
    assert sheets_resp.status_code == 201
    assert sheets_resp.json()["status"] == "active"

    crm_resp = client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "CRM",
            "auth_type": "api_key",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat-valid-token-12345"},
        },
        headers=headers,
    )
    assert crm_resp.status_code == 201
    assert crm_resp.json()["status"] == "active"

    # Create and publish workflow
    wf_payload = {
        "name": "API Triggered Workflow",
        "definition": {
            "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
            "steps": [
                {
                    "id": "step-1",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "mapping": {
                        "name": "trigger.values.Name",
                        "email": "trigger.values.Email",
                    },
                }
            ],
        },
    }
    wf_create = client.post("/workflows", json=wf_payload, headers=headers)
    wf_id = wf_create.json()["id"]

    # Publish workflow
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Execute workflow via API
    exec_resp = client.post(
        f"/workflows/{wf_id}/execute",
        json={
            "trigger_data": {
                "values": {"Name": "Suresh Raina", "Email": "suresh@raina.in"}
            }
        },
        headers=headers,
    )

    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["status"] == "success"
    assert data["workflow_id"] == wf_id
    assert len(data["steps"]) == 1
    assert data["steps"][0]["status"] == "success"
    assert data["steps"][0]["output_data"]["action"] == "create_lead"
