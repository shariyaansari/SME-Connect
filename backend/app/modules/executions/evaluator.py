from typing import Any

from app.modules.executions.resolver import resolve_path


def _is_empty_val(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, (str, list, dict, set, tuple)):
        return len(val) == 0
    return False


def _to_float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def evaluate_condition(
    field_expr: str,
    operator: str,
    expected_value: Any,
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> bool:
    """
    Evaluates a condition step against runtime execution context.
    Supports all operators without hardcoding connector or domain-specific logic:
      - equals, not_equals
      - contains, not_contains
      - greater_than, less_than, greater_than_or_equal, less_than_or_equal
      - is_empty, is_not_empty
    """
    op = operator.lower().strip()

    # Try resolving runtime value
    try:
        actual_value = resolve_path(field_expr, context, allowed_step_ids)
    except ValueError:
        # If the path could not be resolved (e.g. optional missing field)
        actual_value = None

    if op == "is_empty":
        return _is_empty_val(actual_value)

    if op == "is_not_empty":
        return not _is_empty_val(actual_value)

    if op == "equals":
        if actual_value == expected_value:
            return True
        if actual_value is not None and expected_value is not None:
            return str(actual_value).strip().lower() == str(expected_value).strip().lower()
        return False

    if op == "not_equals":
        if actual_value == expected_value:
            return False
        if actual_value is not None and expected_value is not None:
            return str(actual_value).strip().lower() != str(expected_value).strip().lower()
        return True

    if op == "contains":
        if actual_value is None or expected_value is None:
            return False
        if isinstance(actual_value, (str, bytes)):
            return str(expected_value).lower() in str(actual_value).lower()
        if isinstance(actual_value, (list, tuple, set)):
            return expected_value in actual_value or str(expected_value) in [str(x) for x in actual_value]
        if isinstance(actual_value, dict):
            return str(expected_value) in actual_value
        return str(expected_value).lower() in str(actual_value).lower()

    if op == "not_contains":
        return not evaluate_condition(field_expr, "contains", expected_value, context, allowed_step_ids)

    # Numerical comparisons
    act_num = _to_float(actual_value)
    exp_num = _to_float(expected_value)

    if op == "greater_than":
        if act_num is not None and exp_num is not None:
            return act_num > exp_num
        return str(actual_value or "") > str(expected_value or "")

    if op == "less_than":
        if act_num is not None and exp_num is not None:
            return act_num < exp_num
        return str(actual_value or "") < str(expected_value or "")

    if op == "greater_than_or_equal":
        if act_num is not None and exp_num is not None:
            return act_num >= exp_num
        return str(actual_value or "") >= str(expected_value or "")

    if op == "less_than_or_equal":
        if act_num is not None and exp_num is not None:
            return act_num <= exp_num
        return str(actual_value or "") <= str(expected_value or "")

    raise ValueError(f"Unsupported condition operator: '{operator}'")
