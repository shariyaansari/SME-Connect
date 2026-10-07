import pytest
from app.modules.executions.evaluator import evaluate_condition
from app.modules.executions.resolver import (
    resolve_mapping,
    resolve_path,
    sanitize_data,
    sanitize_error_message,
)
from app.modules.executions.service import (
    execute_workflow,
    get_execution,
    list_executions,
    to_detail_response,
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


# ============================================================================
# Unit Tests: Mapping Resolution & Credential Sanitization (3B.4)
# ============================================================================

def test_mapping_resolver_basic_and_nested():
    context = {
        "trigger": {
            "row_index": 5,
            "values": {
                "Name": "Aarav Sharma",
                "Email": "aarav@example.com",
                "Metadata": {
                    "Source": "Website Inquiry",
                },
            },
        },
        "steps": {},
    }

    # Direct path resolution
    assert resolve_path("trigger.row_index", context) == 5
    assert resolve_path("trigger.values.Name", context) == "Aarav Sharma"
    assert resolve_path("trigger.values.Metadata.Source", context) == "Website Inquiry"

    # Mapping resolution with nested structures
    mapping = {
        "lead_name": "trigger.values.Name",
        "email": "trigger.values.Email",
        "details": {
            "origin": "trigger.values.Metadata.Source",
            "row": "trigger.row_index",
            "static_field": "Active",
        },
        "tags": ["trigger.values.Metadata.Source", "new_lead"],
    }

    resolved = resolve_mapping(mapping, context, allowed_step_ids=set())
    assert resolved == {
        "lead_name": "Aarav Sharma",
        "email": "aarav@example.com",
        "details": {
            "origin": "Website Inquiry",
            "row": 5,
            "static_field": "Active",
        },
        "tags": ["Website Inquiry", "new_lead"],
    }


def test_mapping_resolver_previous_step_output():
    context = {
        "trigger": {"order_id": "ORD-99"},
        "steps": {
            "step-1": {
                "lead_id": "lead_12345",
                "customer": {
                    "email": "customer@corp.com",
                },
            },
        },
    }

    # Preceding step allowed
    resolved = resolve_path("steps.step-1.lead_id", context, allowed_step_ids={"step-1"})
    assert resolved == "lead_12345"

    nested = resolve_path("steps.step-1.customer.email", context, allowed_step_ids={"step-1"})
    assert nested == "customer@corp.com"


def test_mapping_resolver_rejects_future_step_reference():
    context = {
        "trigger": {"id": 1},
        "steps": {"step-1": {"status": "ok"}},
    }

    # Reference to step-2 which is a future step (not in allowed preceding steps)
    with pytest.raises(ValueError, match="not an executed preceding step"):
        resolve_path("steps.step-2.id", context, allowed_step_ids={"step-1"})


def test_mapping_resolver_rejects_invalid_path():
    context = {"trigger": {"val": 10}, "steps": {}}

    with pytest.raises(ValueError, match="not found in trigger"):
        resolve_path("trigger.missing_key", context)

    with pytest.raises(ValueError, match="Expressions must start with"):
        resolve_path("invalid_prefix.something", context)


def test_credential_sanitizer():
    dirty_data = {
        "api_key": "secret_live_key_9999",
        "client_secret": "super_secret_oauth_token",
        "user_email": "test@example.com",
        "nested": {
            "password": "pass1234Password!",
            "public_id": "user_456",
        },
    }
    clean_data = sanitize_data(dirty_data)
    assert clean_data["api_key"] == "••••••••"
    assert clean_data["client_secret"] == "••••••••"
    assert clean_data["user_email"] == "test@example.com"
    assert clean_data["nested"]["password"] == "••••••••"
    assert clean_data["nested"]["public_id"] == "user_456"

    dirty_err = "Failed authentication: Bearer eyJhbGciOiJIUzI1NiJ9 with key=my_secret_token"
    clean_err = sanitize_error_message(dirty_err)
    assert "eyJhbGciOiJIUzI1NiJ9" not in clean_err
    assert "my_secret_token" not in clean_err


# ============================================================================
# Unit Tests: Condition Evaluation (3B.5)
# ============================================================================

def test_condition_evaluation_all_operators():
    context = {
        "trigger": {
            "status": "APPROVED",
            "amount": 250,
            "email": "test@domain.com",
            "empty_field": "",
            "null_field": None,
            "tags": ["vip", "enterprise"],
        },
        "steps": {
            "step-1": {"score": 85},
        },
    }

    # equals & not_equals
    assert evaluate_condition("trigger.status", "equals", "APPROVED", context) is True
    assert evaluate_condition("trigger.status", "equals", "rejected", context) is False
    assert evaluate_condition("trigger.status", "not_equals", "REJECTED", context) is True

    # contains & not_contains
    assert evaluate_condition("trigger.email", "contains", "domain.com", context) is True
    assert evaluate_condition("trigger.tags", "contains", "vip", context) is True
    assert evaluate_condition("trigger.email", "not_contains", "gmail", context) is True

    # greater_than & less_than
    assert evaluate_condition("trigger.amount", "greater_than", 100, context) is True
    assert evaluate_condition("trigger.amount", "greater_than", 500, context) is False
    assert evaluate_condition("trigger.amount", "less_than", 300, context) is True
    assert evaluate_condition("trigger.amount", "greater_than_or_equal", 250, context) is True
    assert evaluate_condition("trigger.amount", "less_than_or_equal", 250, context) is True

    # steps reference
    assert evaluate_condition("steps.step-1.score", "greater_than", 80, context, allowed_step_ids={"step-1"}) is True

    # is_empty & is_not_empty
    assert evaluate_condition("trigger.empty_field", "is_empty", None, context) is True
    assert evaluate_condition("trigger.null_field", "is_empty", None, context) is True
    assert evaluate_condition("trigger.status", "is_empty", None, context) is False
    assert evaluate_condition("trigger.email", "is_not_empty", None, context) is True


# ============================================================================
# Integration Tests: Workflow Execution Service (3B.1, 3B.3, 3B.6)
# ============================================================================

def test_execution_service_published_workflow_success(client, db_session):
    headers = register_and_login(client, "Execution Admin", "exec_admin@test.com")
    org_resp = client.post("/organizations", json={"name": "Execution Org"}, headers=headers)
    org_id = org_resp.json()["id"]

    # Add active connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Exec Sheets",
            "config": {"spreadsheet_id": "sheet_exec_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_123"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Exec CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_key_456"},
        },
        headers=headers,
    )

    # Create workflow
    payload = {
        "name": "Lead Flow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_exec_123"},
            },
            "steps": [
                {
                    "id": "check-email",
                    "type": "condition",
                    "field": "trigger.values.Email",
                    "operator": "is_not_empty",
                    "value": None,
                },
                {
                    "id": "create-crm-lead",
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
    wf_resp = client.post("/workflows", json=payload, headers=headers)
    wf_id = wf_resp.json()["id"]

    # Publish workflow
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Trigger execution
    trigger_data = {
        "row_index": 2,
        "values": {
            "Name": "Vikram Patel",
            "Email": "vikram@enterprise.in",
        },
    }

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data=trigger_data,
        organization_id=org_id,
    )

    assert execution.id is not None
    assert execution.workflow_id == wf_id
    assert execution.organization_id == org_id
    assert execution.status == "success"
    assert execution.completed_at is not None
    assert execution.error_message is None

    # Verify steps
    steps = sorted(execution.step_executions, key=lambda s: s.step_index)
    assert len(steps) == 2

    # Step 1: condition
    assert steps[0].step_id == "check-email"
    assert steps[0].status == "success"
    assert steps[0].output_data.get("condition_met") is True

    # Step 2: action
    assert steps[1].step_id == "create-crm-lead"
    assert steps[1].status == "success"
    assert steps[1].input_data.get("name") == "Vikram Patel"
    assert steps[1].input_data.get("email") == "vikram@enterprise.in"
    assert steps[1].output_data.get("success") is True
    assert steps[1].output_data.get("lead_id") is not None

    # Credentials must NOT appear in step or execution records
    detail = to_detail_response(execution)
    dump_str = detail.model_dump_json()
    assert "sec_123" not in dump_str
    assert "pat_key_456" not in dump_str


def test_execution_draft_workflow_rejection(client, db_session):
    headers = register_and_login(client, "Draft Admin", "draft_admin@test.com")
    org_resp = client.post("/organizations", json={"name": "Draft Org"}, headers=headers)
    org_id = org_resp.json()["id"]

    # Create active connections
    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Draft Sheet",
            "config": {"spreadsheet_id": "sheet_1"},
            "credentials": {"client_id": "svc@g.com", "client_secret": "sec"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Draft CRM",
            "config": {},
            "credentials": {"api_key": "key"},
        },
        headers=headers,
    )

    # Create workflow in draft state
    wf_resp = client.post(
        "/workflows",
        json={
            "name": "Draft Flow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [
                    {
                        "id": "step-1",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "config": {},
                        "mapping": {"name": "trigger.name"},
                    }
                ],
            },
        },
        headers=headers,
    )
    wf_id = wf_resp.json()["id"]

    # Attempting to execute draft workflow must fail
    with pytest.raises(ValueError, match="Cannot execute workflow with status 'draft'"):
        execute_workflow(db=db_session, workflow_id=wf_id, trigger_data={"name": "Test"}, organization_id=org_id)


def test_execution_paused_workflow_rejection(client, db_session):
    headers = register_and_login(client, "Pause Admin", "pause_admin@test.com")
    org_resp = client.post("/organizations", json={"name": "Pause Org"}, headers=headers)
    org_id = org_resp.json()["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Pause Sheet",
            "config": {"spreadsheet_id": "s"},
            "credentials": {"client_id": "c", "client_secret": "s"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Pause CRM",
            "config": {},
            "credentials": {"api_key": "k"},
        },
        headers=headers,
    )

    wf_resp = client.post(
        "/workflows",
        json={
            "name": "Pause Flow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [
                    {
                        "id": "step-1",
                        "type": "action",
                        "connector": "crm",
                        "action": "create_lead",
                        "config": {},
                        "mapping": {"name": "trigger.name"},
                    }
                ],
            },
        },
        headers=headers,
    )
    wf_id = wf_resp.json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=headers)
    client.post(f"/workflows/{wf_id}/pause", headers=headers)

    # Attempting to execute paused workflow must fail
    with pytest.raises(ValueError, match="Cannot execute workflow with status 'paused'"):
        execute_workflow(db=db_session, workflow_id=wf_id, trigger_data={"name": "Test"}, organization_id=org_id)


def test_execution_condition_false_skips_subsequent_steps(client, db_session):
    headers = register_and_login(client, "Condition Admin", "cond_admin@test.com")
    org_resp = client.post("/organizations", json={"name": "Condition Org"}, headers=headers)
    org_id = org_resp.json()["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Cond Sheets",
            "config": {"spreadsheet_id": "s"},
            "credentials": {"client_id": "c", "client_secret": "s"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Cond CRM",
            "config": {},
            "credentials": {"api_key": "k"},
        },
        headers=headers,
    )

    payload = {
        "name": "Condition Filter Flow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
            },
            "steps": [
                {
                    "id": "email-required",
                    "type": "condition",
                    "field": "trigger.values.Email",
                    "operator": "is_not_empty",
                    "value": None,
                },
                {
                    "id": "create-lead",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "config": {},
                    "mapping": {"name": "trigger.values.Name"},
                },
            ],
        },
    }
    wf_id = client.post("/workflows", json=payload, headers=headers).json()["id"]
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Trigger with missing/empty email
    trigger_data = {
        "values": {
            "Name": "Anonymous User",
            "Email": "",
        }
    }

    execution = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data=trigger_data,
        organization_id=org_id,
    )

    assert execution.status == "success"
    steps = sorted(execution.step_executions, key=lambda s: s.step_index)
    assert len(steps) == 2

    # Step 1 condition met is False
    assert steps[0].step_id == "email-required"
    assert steps[0].status == "success"
    assert steps[0].output_data.get("condition_met") is False

    # Step 2 was cleanly skipped
    assert steps[1].step_id == "create-lead"
    assert steps[1].status == "skipped"
    assert steps[1].output_data.get("skipped") is True


def test_execution_organization_isolation(client, db_session):
    # Org 1
    h1 = register_and_login(client, "User 1", "u1@org1.com")
    org1_id = client.post("/organizations", json={"name": "Org 1"}, headers=h1).json()["id"]
    client.post(
        "/connectors",
        json={"connector_slug": "google_sheets", "name": "S1", "config": {"spreadsheet_id": "s"}, "credentials": {"client_id": "c", "client_secret": "s"}},
        headers=h1,
    )
    client.post(
        "/connectors",
        json={"connector_slug": "crm", "name": "C1", "config": {}, "credentials": {"api_key": "k"}},
        headers=h1,
    )
    wf_id1 = client.post(
        "/workflows",
        json={
            "name": "Org 1 Flow",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [{"id": "s1", "type": "action", "connector": "crm", "action": "create_lead", "mapping": {"name": "trigger.name"}}],
            },
        },
        headers=h1,
    ).json()["id"]
    client.post(f"/workflows/{wf_id1}/publish", headers=h1)

    # Org 2
    h2 = register_and_login(client, "User 2", "u2@org2.com")
    org2_id = client.post("/organizations", json={"name": "Org 2"}, headers=h2).json()["id"]

    # Org 2 cannot execute Org 1's workflow
    with pytest.raises(ValueError, match="Workflow not found"):
        execute_workflow(
            db=db_session,
            workflow_id=wf_id1,
            trigger_data={"name": "Test"},
            organization_id=org2_id,
        )


def test_execution_uses_immutable_published_version(client, db_session):
    headers = register_and_login(client, "Immutability Admin", "immut@test.com")
    org_id = client.post("/organizations", json={"name": "Immut Org"}, headers=headers).json()["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Immut Sheet",
            "config": {"spreadsheet_id": "sheet_immut_123"},
            "credentials": {"client_id": "svc@google.com", "client_secret": "sec_123"},
        },
        headers=headers,
    )
    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Immut CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "pat_key_123"},
        },
        headers=headers,
    )

    # Create V1
    wf_id = client.post(
        "/workflows",
        json={
            "name": "Version Test",
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [{"id": "step-v1", "type": "action", "connector": "crm", "action": "create_lead", "mapping": {"name": "trigger.name"}}],
            },
        },
        headers=headers,
    ).json()["id"]
    pub1_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub1_resp.status_code == 200, pub1_resp.text

    # Execution 1 must execute published V1
    exec1 = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"name": "Client V1"},
        organization_id=org_id,
    )
    assert exec1.status == "success"
    assert exec1.step_executions[0].step_id == "step-v1"
    v1_exec_id = exec1.id

    # Edit workflow to create V2 draft with different step
    client.put(
        f"/workflows/{wf_id}",
        json={
            "definition": {
                "trigger": {"connector": "google_sheets", "event": "new_row"},
                "steps": [{"id": "step-v2", "type": "action", "connector": "crm", "action": "create_lead", "mapping": {"name": "trigger.name"}}],
            }
        },
        headers=headers,
    )

    # Publishing V2 makes V2 the active published version
    client.post(f"/workflows/{wf_id}/publish", headers=headers)

    # Execution 2 must execute published V2, containing step-v2
    exec2 = execute_workflow(
        db=db_session,
        workflow_id=wf_id,
        trigger_data={"name": "Client V2"},
        organization_id=org_id,
    )
    assert exec2.status == "success"
    assert exec2.step_executions[0].step_id == "step-v2"

    # Historic execution 1 remains attached to V1 and has step-v1
    exec1_reloaded = get_execution(db=db_session, execution_id=v1_exec_id, organization_id=org_id)
    assert exec1_reloaded.step_executions[0].step_id == "step-v1"
