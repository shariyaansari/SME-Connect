import pytest
from unittest.mock import patch

from app.modules.transformations.engine import (
    evaluate_template,
    evaluate_transformation,
    extract_value,
    get_transformations_catalog,
)
from app.modules.executions.resolver import resolve_mapping
from app.modules.workflows.validation import validate_workflow_definition
from app.modules.executions.service import execute_workflow
from app.database.models import Workflow, WorkflowVersion


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
# 1. Pure Transformation Functions Tests
# ============================================================================

def test_transform_concat():
    context = {"trigger": {"first": "Jane", "last": "Doe"}}
    res = evaluate_transformation(
        {"transform": "concat", "sources": ["trigger.first", "trigger.last"], "separator": " "},
        context,
    )
    assert res == "Jane Doe"

    # Multi-part with literal strings
    res2 = evaluate_transformation(
        {"transform": "concat", "sources": ["trigger.first", " - ", "trigger.last"]},
        context,
    )
    assert res2 == "Jane - Doe"


def test_transform_trim():
    context = {"trigger": {"raw": "   hello world   \n"}}
    res = evaluate_transformation({"transform": "trim", "source": "trigger.raw"}, context)
    assert res == "hello world"


def test_transform_cases():
    context = {"trigger": {"text": "hElLo WoRlD"}}
    assert evaluate_transformation({"transform": "uppercase", "source": "trigger.text"}, context) == "HELLO WORLD"
    assert evaluate_transformation({"transform": "lowercase", "source": "trigger.text"}, context) == "hello world"
    assert evaluate_transformation({"transform": "titlecase", "source": "trigger.text"}, context) == "Hello World"


def test_transform_replace():
    context = {"trigger": {"phone": "+91-98765-43210"}}
    res = evaluate_transformation(
        {"transform": "replace", "source": "trigger.phone", "find": "+91-", "replace_with": ""},
        context,
    )
    assert res == "98765-43210"


def test_transform_substring():
    context = {"trigger": {"code": "ABCD1234EFGH"}}
    res = evaluate_transformation(
        {"transform": "substring", "source": "trigger.code", "start": 0, "end": 4},
        context,
    )
    assert res == "ABCD"

    res_len = evaluate_transformation(
        {"transform": "substring", "source": "trigger.code", "start": 4, "length": 4},
        context,
    )
    assert res_len == "1234"


def test_transform_default_value():
    context = {"trigger": {"empty_str": "", "missing": None, "present": "Valid"}}
    assert evaluate_transformation(
        {"transform": "default_value", "source": "trigger.empty_str", "default": "Fallback"},
        context,
    ) == "Fallback"
    assert evaluate_transformation(
        {"transform": "default_value", "source": "trigger.missing", "default": "Fallback"},
        context,
    ) == "Fallback"
    assert evaluate_transformation(
        {"transform": "default_value", "source": "trigger.non_existent", "default": "Fallback"},
        context,
    ) == "Fallback"
    assert evaluate_transformation(
        {"transform": "default_value", "source": "trigger.present", "default": "Fallback"},
        context,
    ) == "Valid"


def test_transform_coercion():
    context = {"trigger": {"num_str": "$1,250.75", "int_str": "42.8", "bool_str": "true", "val": 123}}
    # to_string
    assert evaluate_transformation({"transform": "to_string", "source": "trigger.val"}, context) == "123"
    # to_number
    assert evaluate_transformation({"transform": "to_number", "source": "trigger.num_str"}, context) == 1250.75
    # to_integer
    assert evaluate_transformation({"transform": "to_integer", "source": "trigger.int_str"}, context) == 43
    # to_boolean
    assert evaluate_transformation({"transform": "to_boolean", "source": "trigger.bool_str"}, context) is True
    assert evaluate_transformation({"transform": "to_boolean", "source": "trigger.missing", "default": False}, context) is False


def test_transform_format_date():
    context = {"trigger": {"iso_dt": "2026-10-12T14:30:00Z", "standard": "2026-10-12"}}
    res = evaluate_transformation(
        {"transform": "format_date", "source": "trigger.iso_dt", "output_format": "%d-%m-%Y"},
        context,
    )
    assert res == "12-10-2026"

    res2 = evaluate_transformation(
        {"transform": "format_date", "source": "trigger.standard", "output_format": "%B %d, %Y"},
        context,
    )
    assert res2 == "October 12, 2026"


# ============================================================================
# 2. Template String Interpolation Engine Tests
# ============================================================================

def test_template_interpolation():
    context = {
        "trigger": {"values": {"FirstName": "Alice", "LastName": "Smith"}},
        "steps": {"crm_lead": {"id": "LEAD-99"}},
    }
    tmpl = "Dear {{trigger.values.FirstName}} {{trigger.values.LastName}}, Lead ID: {{steps.crm_lead.id}}"
    evaluated = evaluate_template(tmpl, context, allowed_step_ids={"crm_lead"})
    assert evaluated == "Dear Alice Smith, Lead ID: LEAD-99"


def test_template_interpolation_missing_variable():
    context = {"trigger": {"name": "Bob"}}
    tmpl = "Hello {{trigger.name}}, your code is {{trigger.unknown}}"
    evaluated = evaluate_template(tmpl, context)
    assert evaluated == "Hello Bob, your code is "


# ============================================================================
# 3. Execution Mapping Resolver Tests
# ============================================================================

def test_resolver_backward_compatibility():
    context = {"trigger": {"name": "Legacy", "count": 5}}
    mapping = {
        "user_name": "trigger.name",
        "static_field": "fixed_value",
        "nested": {"total": "trigger.count"},
    }
    resolved = resolve_mapping(mapping, context)
    assert resolved == {
        "user_name": "Legacy",
        "static_field": "fixed_value",
        "nested": {"total": 5},
    }


def test_resolver_with_transforms_and_templates():
    context = {
        "trigger": {"first": "clark", "last": "kent", "salary": "50000.5"},
        "steps": {"calc": {"score": 95}},
    }
    mapping = {
        "greeting": "Hi {{trigger.first}} {{trigger.last}}!",
        "full_name": {
            "transform": "concat",
            "sources": ["trigger.first", " ", "trigger.last"],
            "titlecase": False,
        },
        "upper_name": {"transform": "uppercase", "source": "trigger.first"},
        "salary_num": {"transform": "to_number", "source": "trigger.salary"},
        "final_score": "steps.calc.score",
    }
    resolved = resolve_mapping(mapping, context, allowed_step_ids={"calc"})
    assert resolved["greeting"] == "Hi clark kent!"
    assert resolved["full_name"] == "clark kent"
    assert resolved["upper_name"] == "CLARK"
    assert resolved["salary_num"] == 50000.5
    assert resolved["final_score"] == 95


# ============================================================================
# 4. Workflow Mapping Validation Tests
# ============================================================================

def test_validation_accepts_valid_transform_and_template():
    wf_dict = {
        "name": "Transform WF",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "hourly", "timezone": "UTC"}},
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "email": "user@example.com",
                    "full_name": {
                        "transform": "concat",
                        "sources": ["trigger.first", "trigger.last"],
                    },
                    "welcome_note": "Welcome {{trigger.first}}!",
                },
            }
        ],
    }
    result = validate_workflow_definition(wf_dict)
    assert result.valid is True
    assert len(result.errors) == 0


def test_validation_rejects_forward_reference_in_template():
    wf_dict = {
        "name": "Invalid Template WF",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "hourly", "timezone": "UTC"}},
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "note": "Lead was created by {{steps.step-2.author}}",  # Forward ref to step-2
                },
            },
            {
                "id": "step-2",
                "type": "action",
                "connector": "google_sheets",
                "action": "append_row",
                "mapping": {"spreadsheet_id": "sheet-1"},
            },
        ],
    }
    result = validate_workflow_definition(wf_dict)
    assert result.valid is False
    assert any("step-2" in err.message and err.code == "INVALID_STEP_REFERENCE" for err in result.errors)


def test_validation_rejects_self_reference_in_transform():
    wf_dict = {
        "name": "Self Ref WF",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "hourly", "timezone": "UTC"}},
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "name": {"transform": "uppercase", "source": "steps.step-1.output"},
                },
            }
        ],
    }
    result = validate_workflow_definition(wf_dict)
    assert result.valid is False
    assert any(err.code == "SELF_REFERENCE_MAPPING" for err in result.errors)


def test_validation_rejects_unsupported_transformation():
    wf_dict = {
        "name": "Unknown Transform WF",
        "trigger": {"type": "schedule", "event": "scheduled", "config": {"frequency": "hourly", "timezone": "UTC"}},
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "val": {"transform": "quantum_encryption", "source": "trigger.data"},
                },
            }
        ],
    }
    result = validate_workflow_definition(wf_dict)
    assert result.valid is False
    assert any(err.code == "UNSUPPORTED_TRANSFORMATION" for err in result.errors)


# ============================================================================
# 5. Catalog & Mapping Preview API Tests
# ============================================================================

def test_transform_catalog_endpoint(client):
    headers = register_and_login(client, "Catalog User", "catalog_user@example.com")
    resp = client.get("/workflows/transforms/catalog", headers=headers)
    assert resp.status_code == 200
    catalog = resp.json()
    assert len(catalog) >= 13
    types = {item["type"] for item in catalog}
    assert "concat" in types
    assert "format_date" in types
    assert "to_number" in types


def test_mapping_preview_endpoint(client):
    headers = register_and_login(client, "Preview User", "preview_user@example.com")
    payload = {
        "mapping": {
            "full_name": {
                "transform": "concat",
                "sources": ["trigger.values.FirstName", " ", "trigger.values.LastName"],
            },
            "greeting": "Hello {{trigger.values.FirstName}}!",
            "status_upper": {"transform": "uppercase", "source": "trigger.values.Status"},
            "missing_field": {"transform": "default_value", "source": "trigger.values.NonExistent", "default": "N/A"},
        },
        "sample_context": {
            "trigger": {
                "values": {
                    "FirstName": "Sarah",
                    "LastName": "Connor",
                    "Status": "active",
                }
            }
        },
    }
    resp = client.post("/workflows/mapping/preview", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["fields_evaluated"] == 4
    output = data["output"]
    assert output["full_name"] == "Sarah Connor"
    assert output["greeting"] == "Hello Sarah!"
    assert output["status_upper"] == "ACTIVE"
    assert output["missing_field"] == "N/A"


# ============================================================================
# 6. End-to-End Workflow Execution Integration
# ============================================================================

def test_workflow_execution_with_transformations_and_templates(client, db_session):
    from app.modules.connectors.adapters.crm import CRMAdapter

    headers = register_and_login(client, "Runner M8", "runner_m8@test.com")
    org_resp = client.post("/organizations", json={"name": "Runner M8 Org"}, headers=headers)
    org_id = org_resp.json()["id"]

    client.post(
        "/connectors",
        json={
            "connector_slug": "google_sheets",
            "name": "Orders Sheet",
            "config": {"spreadsheet_id": "sheet_1"},
            "credentials": {"client_id": "svc@g.com", "client_secret": "sec_g_123"},
        },
        headers=headers,
    )

    client.post(
        "/connectors",
        json={
            "connector_slug": "crm",
            "name": "Hubspot CRM",
            "config": {"crm_provider": "HubSpot"},
            "credentials": {"api_key": "sec_key_123"},
        },
        headers=headers,
    )

    wf_payload = {
        "name": "E2E Transform Workflow",
        "definition": {
            "trigger": {
                "connector": "google_sheets",
                "event": "new_row",
                "config": {"spreadsheet_id": "sheet_1"},
            },
            "steps": [
                {
                    "id": "step_crm",
                    "type": "action",
                    "connector": "crm",
                    "action": "create_lead",
                    "mapping": {
                        "name": {
                            "transform": "concat",
                            "sources": ["trigger.row.First", " ", "trigger.row.Last"],
                        },
                        "email": {
                            "transform": "lowercase",
                            "source": "trigger.row.Email",
                        },
                    },
                }
            ],
        },
    }
    wf_resp = client.post("/workflows", json=wf_payload, headers=headers)
    assert wf_resp.status_code == 201
    wf_id = wf_resp.json()["id"]

    pub_resp = client.post(f"/workflows/{wf_id}/publish", headers=headers)
    assert pub_resp.status_code == 200

    trigger_data = {
        "row": {
            "First": "Bruce",
            "Last": "Wayne",
            "Email": "BRUCE@WAYNE.CORP",
        }
    }

    with patch.object(CRMAdapter, "execute_action") as mock_crm:
        mock_crm.return_value = {"lead_id": "lead-888", "status": "created"}

        execution = execute_workflow(
            db=db_session,
            workflow_id=wf_id,
            trigger_data=trigger_data,
            organization_id=org_id,
        )

        assert execution.status == "success"
        # Verify action received the transformed arguments
        mock_crm.assert_called_once()
        _, kwargs = mock_crm.call_args
        action_input = kwargs.get("input_data")
        assert action_input["name"] == "Bruce Wayne"
        assert action_input["email"] == "bruce@wayne.corp"
