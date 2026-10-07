import re
from typing import Any

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth_token",
    "private_key",
    "client_secret",
)


def sanitize_data(data: Any) -> Any:
    """
    Recursively sanitize dictionaries and lists to guarantee credential values
    never appear in execution records, API responses, or logs.
    """
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "••••••••"
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


def sanitize_error_message(msg: str | None) -> str | None:
    """Strip or mask any token/credential patterns in error messages."""
    if not msg:
        return msg
    # Mask common bearer tokens / jwt / hex / api keys / secrets
    cleaned = re.sub(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", r"\1••••••••", msg, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"((?:api[_-]?key|client[_-]?secret|auth[_-]?token|secret|password|key)[=:\s]+['\"]?)[A-Za-z0-9_\-\.]+(?!••••••••)",
        r"\1••••••••",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def resolve_path(
    path: str,
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> Any:
    """
    Resolves a single path expression against runtime execution context.

    Supported patterns:
      - 'trigger.<path>' (e.g. 'trigger.values.Name', 'trigger.row_index')
      - 'steps.<step_id>.<path>' (e.g. 'steps.step-1.lead_id')

    Rejects:
      - Future step references (steps not in allowed_step_ids)
      - Non-existent paths or keys
      - Malformed expressions
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Mapping path must be a non-empty string")

    path = path.strip()
    allowed_set = set(allowed_step_ids) if allowed_step_ids is not None else None

    if path.startswith("trigger."):
        parts = path.split(".")[1:]
        if not parts:
            raise ValueError(f"Malformed trigger mapping path '{path}'")
        curr = context.get("trigger", {})
        for idx, part in enumerate(parts):
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
                curr = curr[int(part)]
            else:
                available = list(curr.keys()) if isinstance(curr, dict) else "non-dict"
                raise ValueError(
                    f"Mapping path '{path}' could not be resolved: key '{part}' not found in trigger data. "
                    f"Available keys: {available}"
                )
        return curr

    elif path.startswith("steps."):
        parts = path.split(".")[1:]
        if len(parts) < 2:
            raise ValueError(
                f"Malformed step mapping path '{path}'. Expected format 'steps.<step_id>.<property>'"
            )
        target_step_id = parts[0]

        # Enforce DAG invariant: must be in preceding executed steps
        if allowed_set is not None and target_step_id not in allowed_set:
            raise ValueError(
                f"Invalid mapping path '{path}': step '{target_step_id}' is not an executed preceding step. "
                f"Allowed preceding steps: {sorted(list(allowed_set)) or ['none']}"
            )

        steps_context = context.get("steps", {})
        if target_step_id not in steps_context:
            raise ValueError(
                f"Step '{target_step_id}' output not found in execution context"
            )

        curr = steps_context[target_step_id]
        for part in parts[1:]:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            elif isinstance(curr, list) and part.isdigit() and int(part) < len(curr):
                curr = curr[int(part)]
            else:
                available = list(curr.keys()) if isinstance(curr, dict) else "non-dict"
                raise ValueError(
                    f"Mapping path '{path}' could not be resolved: key '{part}' not found in step '{target_step_id}' output. "
                    f"Available keys: {available}"
                )
        return curr

    else:
        raise ValueError(
            f"Invalid mapping path '{path}'. Expressions must start with 'trigger.' or 'steps.'"
        )


def resolve_mapping(
    mapping: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> dict[str, Any]:
    """
    Recursively resolves arbitrary mapping dictionaries against execution context.
    Operates on arbitrary JSON data without hardcoding any connector or field names.
    """
    if not mapping:
        return {}

    resolved: dict[str, Any] = {}
    for target_key, expr in mapping.items():
        if isinstance(expr, str):
            if expr.startswith("trigger.") or expr.startswith("steps."):
                resolved[target_key] = resolve_path(expr, context, allowed_step_ids)
            else:
                # Static literal string
                resolved[target_key] = expr
        elif isinstance(expr, dict):
            resolved[target_key] = resolve_mapping(expr, context, allowed_step_ids)
        elif isinstance(expr, list):
            resolved_list = []
            for item in expr:
                if isinstance(item, str) and (item.startswith("trigger.") or item.startswith("steps.")):
                    resolved_list.append(resolve_path(item, context, allowed_step_ids))
                elif isinstance(item, dict):
                    resolved_list.append(resolve_mapping(item, context, allowed_step_ids))
                else:
                    resolved_list.append(item)
            resolved[target_key] = resolved_list
        else:
            resolved[target_key] = expr

    return resolved
