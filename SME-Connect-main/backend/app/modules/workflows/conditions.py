from typing import Any

from app.modules.workflows.mapping import MappingResolutionError, resolve_path
from app.modules.workflows.schemas import ConditionOperator, ConditionStepDefinition


def _is_empty(val: Any) -> bool:
    """Returns True if the value is None or an empty collection/string."""
    if val is None:
        return True
    if isinstance(val, (str, list, dict, set, tuple)):
        return len(val) == 0
    return False


def evaluate_condition_step(step: ConditionStepDefinition, context: dict[str, Any]) -> bool:
    """
    Evaluates a condition step against the runtime execution context.
    
    Operates generically on arbitrary resolved runtime values without hardcoding
    any connector slugs, app names, or schema types.
    """
    try:
        actual = resolve_path(step.field, context)
    except MappingResolutionError:
        actual = None

    expected = step.value
    op = step.operator
    op_val = op.value if isinstance(op, ConditionOperator) else str(op)

    if op_val == ConditionOperator.IS_EMPTY.value:
        return _is_empty(actual)

    if op_val == ConditionOperator.IS_NOT_EMPTY.value:
        return not _is_empty(actual)

    if actual is None and expected is not None:
        return op_val == ConditionOperator.NOT_EQUALS.value

    if op_val == ConditionOperator.EQUALS.value:
        if type(actual) != type(expected) and actual is not None and expected is not None:
            return str(actual).strip() == str(expected).strip()
        return actual == expected

    if op_val == ConditionOperator.NOT_EQUALS.value:
        if type(actual) != type(expected) and actual is not None and expected is not None:
            return str(actual).strip() != str(expected).strip()
        return actual != expected

    if op_val == ConditionOperator.CONTAINS.value:
        if actual is None:
            return False
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return str(expected) in str(actual)

    if op_val == ConditionOperator.NOT_CONTAINS.value:
        if actual is None:
            return True
        if isinstance(actual, (list, tuple, set)):
            return expected not in actual
        return str(expected) not in str(actual)

    # Numerical comparisons
    try:
        num_actual = float(actual)
        num_expected = float(expected)
    except (TypeError, ValueError):
        return False

    if op_val == ConditionOperator.GREATER_THAN.value:
        return num_actual > num_expected
    if op_val == ConditionOperator.LESS_THAN.value:
        return num_actual < num_expected
    if op_val == ConditionOperator.GREATER_THAN_OR_EQUAL.value:
        return num_actual >= num_expected
    if op_val == ConditionOperator.LESS_THAN_OR_EQUAL.value:
        return num_actual <= num_expected

    raise ValueError(f"Unsupported condition operator '{op}'")
