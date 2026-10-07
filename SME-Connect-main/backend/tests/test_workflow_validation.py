import inspect
import pytest

from app.modules.workflows import schemas, validation
from app.modules.workflows.schemas import WorkflowDefinition
from app.modules.workflows.validation import (
    WorkflowValidationError,
    validate_workflow_definition,
    validate_workflow_or_raise,
)


# ============================================================================
# 1. Structural Tests
# ============================================================================

def test_valid_workflow():
    """✅ valid workflow: Complete, well-formed Golden Workflow."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
            "config": {
                "spreadsheet_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
                "sheet_name": "Inquiries",
            },
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
                    "email": "trigger.values.Email",
                    "phone": "trigger.values.Phone",
                },
            }
        ],
    }

    result = validate_workflow_definition(definition)
    assert result.valid is True
    assert len(result.errors) == 0

    wf = validate_workflow_or_raise(definition)
    assert isinstance(wf, WorkflowDefinition)
    assert wf.trigger.connector == "google_sheets"


def test_missing_trigger():
    """✅ missing trigger: Workflow without a trigger must fail."""
    definition = {
        "steps": [
            {
                "id": "create-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ]
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    assert any("trigger" in e.path for e in result.errors)


def test_empty_steps():
    """✅ empty steps: Workflow with steps: [] must fail."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    assert any("steps" in e.path for e in result.errors)


def test_missing_connector_in_step():
    """✅ missing connector: Action step without connector must fail."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    assert any("connector" in e.path for e in result.errors)


def test_missing_action_in_step():
    """✅ missing action: Action step without action must fail."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    assert any("action" in e.path for e in result.errors)


def test_invalid_step_type():
    """✅ invalid step type: Step with unsupported type must fail."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "unsupported_loop",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    assert any("steps" in e.path for e in result.errors)
    assert any("type" in e.message or e.code == "union_tag_invalid" for e in result.errors)


# ============================================================================
# 2. ID Tests
# ============================================================================

def test_valid_step_ids():
    """✅ valid step IDs: Alphanumeric, underscores, hyphens are accepted."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step_1-A",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
            {
                "id": "step2B_final",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_invalid_step_id():
    """❌ invalid step ID: Spaces or special characters are rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step with spaces!",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "INVALID_STEP_ID_FORMAT" in codes


def test_duplicate_step_id():
    """❌ duplicate step ID: Identical IDs in the same workflow are rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "create-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
            {
                "id": "create-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "DUPLICATE_STEP_ID" in codes


# ============================================================================
# 3. Connector Capability Tests
# ============================================================================

def test_registered_connector():
    """✅ registered connector: Known connector in registry passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_unknown_connector():
    """❌ unknown connector: Unregistered connector is rejected."""
    definition = {
        "trigger": {
            "connector": "unregistered_external_app",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "UNKNOWN_CONNECTOR" in codes


# ============================================================================
# 4. Trigger Tests
# ============================================================================

def test_supported_trigger():
    """✅ supported trigger: Trigger event supported by connector passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_unsupported_trigger():
    """❌ unsupported trigger: Event not offered by connector is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "non_existent_event_slug",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "UNSUPPORTED_TRIGGER" in codes


# ============================================================================
# 5. Action Tests
# ============================================================================

def test_supported_action():
    """✅ supported action: Action offered by connector passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_unsupported_action():
    """❌ unsupported action: Action not offered by connector is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "fake_action_slug",
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "UNSUPPORTED_ACTION" in codes


# ============================================================================
# 6. Mapping Tests
# ============================================================================

def test_mapping_trigger_field():
    """✅ trigger.field: Mapping from trigger source paths passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "email": "trigger.values.Email",
                    "full_name": "trigger.values.Name",
                },
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_mapping_previous_step_field():
    """✅ previous-step.field: Mapping from preceding step output passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {"email": "trigger.values.Email"},
            },
            {
                "id": "step-2",
                "type": "action",
                "connector": "whatsapp",
                "action": "send_text",
                "mapping": {
                    "to": "trigger.values.Phone",
                    "message": "steps.step-1.lead_id",
                },
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_mapping_malformed_path():
    """❌ malformed path: trigger. or steps. without property is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "email": "trigger.",  # Incomplete path
                },
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "MALFORMED_MAPPING_PATH" in codes


def test_mapping_self_reference():
    """❌ self-reference: Step mapping to its own output is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "reference": "steps.step-lead.id",
                },
            }
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "SELF_REFERENCE_MAPPING" in codes


def test_mapping_future_step_reference():
    """❌ future-step reference: Step 1 referencing Step 2 is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "step-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
                "mapping": {
                    "id": "steps.step-2.lead_id",  # Invalid forward reference
                },
            },
            {
                "id": "step-2",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "INVALID_STEP_REFERENCE" in codes

    with pytest.raises(WorkflowValidationError):
        validate_workflow_or_raise(definition)


# ============================================================================
# 7. Condition Tests
# ============================================================================

def test_condition_valid():
    """✅ valid condition: Condition referencing trigger.status with operator equals passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "filter-qualified",
                "type": "condition",
                "field": "trigger.status",
                "operator": "equals",
                "value": "Qualified",
            },
            {
                "id": "create-lead",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


def test_condition_malformed_trigger_reference():
    """❌ malformed trigger. reference: field = 'trigger.' must be rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "cond-1",
                "type": "condition",
                "field": "trigger.",  # Incomplete path
                "operator": "equals",
                "value": "active",
            },
            {
                "id": "action-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "MALFORMED_CONDITION_PATH" in codes


def test_condition_invalid_previous_step_reference():
    """❌ invalid previous-step reference: field = 'steps.nonexistent.status' is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "cond-1",
                "type": "condition",
                "field": "steps.nonexistent.status",  # Step does not precede
                "operator": "equals",
                "value": "active",
            },
            {
                "id": "action-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "INVALID_STEP_REFERENCE" in codes


def test_condition_missing_value_for_equals():
    """❌ missing value for equals: Binary operator equals without value is rejected."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "cond-1",
                "type": "condition",
                "field": "trigger.status",
                "operator": "equals",
                "value": None,
            },
            {
                "id": "action-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is False
    codes = [e.code for e in result.errors]
    assert "MISSING_CONDITION_VALUE" in codes


def test_condition_no_value_for_is_empty():
    """✅ no value for is_empty: Unary operator is_empty with value None passes."""
    definition = {
        "trigger": {
            "connector": "google_sheets",
            "event": "new_row",
        },
        "steps": [
            {
                "id": "check-empty",
                "type": "condition",
                "field": "trigger.phone",
                "operator": "is_empty",
                "value": None,
            },
            {
                "id": "action-1",
                "type": "action",
                "connector": "crm",
                "action": "create_lead",
            },
        ],
    }
    result = validate_workflow_definition(definition)
    assert result.valid is True


# ============================================================================
# 8. Architectural Invariant Test
# ============================================================================

def test_no_hardcoded_connector_logic_in_workflow_module():
    """
    Workflow validation must resolve connectors dynamically through
    the connector registry rather than checking specific connector slugs.
    """
    validation_code = inspect.getsource(validation)

    assert 'if connector == "google_sheets"' not in validation_code
    assert 'if connector == "crm"' not in validation_code
    assert 'connector == "google_sheets"' not in validation_code
    assert 'connector == "crm"' not in validation_code
