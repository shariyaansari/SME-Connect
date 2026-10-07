import pytest
from app.modules.workflows.mapping import (
    MappingResolutionError,
    resolve_mapping,
    resolve_path,
)


def test_resolve_trigger_paths():
    context = {
        "trigger": {
            "row_index": 42,
            "values": {
                "Name": "Deepak Sharma",
                "Email": "deepak@sme.com",
                "Phone": "+91-9876543210",
            },
        },
        "steps": {},
    }

    assert resolve_path("trigger.row_index", context) == 42
    assert resolve_path("trigger.values.Name", context) == "Deepak Sharma"
    assert resolve_path("trigger.values.Email", context) == "deepak@sme.com"


def test_resolve_nested_dictionary_and_list_mapping():
    context = {
        "trigger": {
            "order": {
                "items": [
                    {"sku": "SKU-001", "qty": 2},
                    {"sku": "SKU-002", "qty": 5},
                ],
                "customer": {
                    "address": {
                        "city": "Bengaluru",
                        "country": "India",
                    }
                },
            }
        },
        "steps": {},
    }

    assert resolve_path("trigger.order.items.0.sku", context) == "SKU-001"
    assert resolve_path("trigger.order.items.1.qty", context) == 5
    assert resolve_path("trigger.order.customer.address.city", context) == "Bengaluru"


def test_resolve_previous_step_mapping():
    context = {
        "trigger": {"lead_id": "raw_101"},
        "steps": {
            "step-1": {
                "success": True,
                "lead_id": "crm_lead_889",
                "created_contact": {
                    "name": "Ananya Roy",
                    "email": "ananya@example.com",
                },
            }
        },
    }

    assert resolve_path("steps.step-1.lead_id", context) == "crm_lead_889"
    assert resolve_path("steps.step-1.created_contact.name", context) == "Ananya Roy"
    assert resolve_path("steps.step-1.created_contact.email", context) == "ananya@example.com"


def test_future_or_unexecuted_step_reference_rejected():
    context = {
        "trigger": {"name": "Test"},
        "steps": {
            "step-1": {"status": "ok"},
        },
    }

    # Attempting to reference step-2 which has not run yet
    with pytest.raises(MappingResolutionError) as exc_info:
        resolve_path("steps.step-2.lead_id", context)

    assert "step-2" in str(exc_info.value)
    assert "not available" in str(exc_info.value)


def test_invalid_trigger_path_rejected():
    context = {
        "trigger": {"values": {"Name": "Test"}},
        "steps": {},
    }

    with pytest.raises(MappingResolutionError) as exc_info:
        resolve_path("trigger.values.NonExistentField", context)

    assert "NonExistentField" in str(exc_info.value)


def test_full_mapping_structure_resolution():
    context = {
        "trigger": {
            "values": {
                "CustomerName": "Vikram Patel",
                "WorkEmail": "vikram@enterprise.in",
                "Mobile": "9199887766",
            }
        },
        "steps": {
            "crm-create": {
                "lead_id": "lead_9999",
            }
        },
    }

    mapping_def = {
        "name": "trigger.values.CustomerName",
        "email": "trigger.values.WorkEmail",
        "phone": "trigger.values.Mobile",
        "external_lead_ref": "steps.crm-create.lead_id",
        "static_source": "SME-Connect-Automation",
        "static_priority": 1,
        "metadata": {
            "original_name": "trigger.values.CustomerName",
            "tags": ["auto-generated", "v1"],
        },
    }

    resolved = resolve_mapping(mapping_def, context)

    assert resolved["name"] == "Vikram Patel"
    assert resolved["email"] == "vikram@enterprise.in"
    assert resolved["phone"] == "9199887766"
    assert resolved["external_lead_ref"] == "lead_9999"
    assert resolved["static_source"] == "SME-Connect-Automation"
    assert resolved["static_priority"] == 1
    assert resolved["metadata"]["original_name"] == "Vikram Patel"
    assert resolved["metadata"]["tags"] == ["auto-generated", "v1"]
