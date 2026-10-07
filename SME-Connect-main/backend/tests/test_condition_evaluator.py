import pytest
from app.modules.workflows.conditions import evaluate_condition_step
from app.modules.workflows.schemas import ConditionOperator, ConditionStepDefinition


def test_condition_equals_and_not_equals():
    context = {
        "trigger": {"status": "active", "code": 100},
        "steps": {},
    }

    # Equals success
    step_eq = ConditionStepDefinition(
        id="check-status",
        field="trigger.status",
        operator=ConditionOperator.EQUALS,
        value="active",
    )
    assert evaluate_condition_step(step_eq, context) is True

    # Equals failure
    step_eq_fail = ConditionStepDefinition(
        id="check-status",
        field="trigger.status",
        operator=ConditionOperator.EQUALS,
        value="inactive",
    )
    assert evaluate_condition_step(step_eq_fail, context) is False

    # Not equals success
    step_neq = ConditionStepDefinition(
        id="check-status",
        field="trigger.status",
        operator=ConditionOperator.NOT_EQUALS,
        value="closed",
    )
    assert evaluate_condition_step(step_neq, context) is True


def test_condition_contains_and_not_contains():
    context = {
        "trigger": {"email": "contact@bigcorp.com", "tags": ["vip", "inbound"]},
        "steps": {},
    }

    # String contains
    step_contains = ConditionStepDefinition(
        id="check-domain",
        field="trigger.email",
        operator=ConditionOperator.CONTAINS,
        value="@bigcorp.com",
    )
    assert evaluate_condition_step(step_contains, context) is True

    # List contains
    step_list_contains = ConditionStepDefinition(
        id="check-tag",
        field="trigger.tags",
        operator=ConditionOperator.CONTAINS,
        value="vip",
    )
    assert evaluate_condition_step(step_list_contains, context) is True

    # Not contains
    step_not_contains = ConditionStepDefinition(
        id="check-spam",
        field="trigger.email",
        operator=ConditionOperator.NOT_CONTAINS,
        value="spam",
    )
    assert evaluate_condition_step(step_not_contains, context) is True


def test_condition_numerical_comparisons():
    context = {
        "trigger": {"amount": 2500, "discount": 10.5},
        "steps": {},
    }

    # Greater than
    step_gt = ConditionStepDefinition(
        id="check-amount-gt",
        field="trigger.amount",
        operator=ConditionOperator.GREATER_THAN,
        value=1000,
    )
    assert evaluate_condition_step(step_gt, context) is True

    # Less than
    step_lt = ConditionStepDefinition(
        id="check-amount-lt",
        field="trigger.discount",
        operator=ConditionOperator.LESS_THAN,
        value=20.0,
    )
    assert evaluate_condition_step(step_lt, context) is True

    # Greater than or equal
    step_gte = ConditionStepDefinition(
        id="check-gte",
        field="trigger.amount",
        operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
        value=2500,
    )
    assert evaluate_condition_step(step_gte, context) is True

    # Less than or equal
    step_lte = ConditionStepDefinition(
        id="check-lte",
        field="trigger.amount",
        operator=ConditionOperator.LESS_THAN_OR_EQUAL,
        value=2500,
    )
    assert evaluate_condition_step(step_lte, context) is True


def test_condition_is_empty_and_is_not_empty():
    context = {
        "trigger": {
            "name": "Jane",
            "empty_notes": "",
            "null_phone": None,
            "empty_list": [],
        },
        "steps": {},
    }

    # is_empty for empty string
    step_empty_str = ConditionStepDefinition(
        id="check-notes",
        field="trigger.empty_notes",
        operator=ConditionOperator.IS_EMPTY,
    )
    assert evaluate_condition_step(step_empty_str, context) is True

    # is_empty for None
    step_null = ConditionStepDefinition(
        id="check-phone",
        field="trigger.null_phone",
        operator=ConditionOperator.IS_EMPTY,
    )
    assert evaluate_condition_step(step_null, context) is True

    # is_empty for missing path
    step_missing = ConditionStepDefinition(
        id="check-missing",
        field="trigger.does_not_exist",
        operator=ConditionOperator.IS_EMPTY,
    )
    assert evaluate_condition_step(step_missing, context) is True

    # is_not_empty
    step_not_empty = ConditionStepDefinition(
        id="check-name",
        field="trigger.name",
        operator=ConditionOperator.IS_NOT_EMPTY,
    )
    assert evaluate_condition_step(step_not_empty, context) is True

    step_not_empty_fail = ConditionStepDefinition(
        id="check-empty-list",
        field="trigger.empty_list",
        operator=ConditionOperator.IS_NOT_EMPTY,
    )
    assert evaluate_condition_step(step_not_empty_fail, context) is False
