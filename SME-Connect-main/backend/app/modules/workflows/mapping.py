from typing import Any


class MappingResolutionError(ValueError):
    """Raised when a field mapping path cannot be resolved from execution context."""
    pass


def resolve_path(path: str, context: dict[str, Any]) -> Any:
    """
    Resolves a dot-delimited expression from the execution context.
    
    Supported root namespaces:
      - trigger.<path>: e.g. trigger.values.Name, trigger.row_index
      - steps.<step_id>.<path>: e.g. steps.step-1.lead_id
    
    Invariants:
      - Operates on arbitrary JSON structures without hardcoding connector or field names.
      - Disallows references to unexecuted or future steps.
      - Never exposes credentials or authorization headers.
    """
    if not isinstance(path, str):
        return path

    if path.startswith("trigger."):
        remainder = path[len("trigger."):]
        if not remainder:
            return context.get("trigger", {})

        curr = context.get("trigger", {})
        tokens = remainder.split(".")
        for idx, token in enumerate(tokens):
            if curr is None:
                raise MappingResolutionError(
                    f"Cannot access property '{token}' from null along path '{path}'"
                )
            if isinstance(curr, dict):
                if token in curr:
                    curr = curr[token]
                else:
                    available = list(curr.keys())
                    raise MappingResolutionError(
                        f"Field '{token}' not found along path '{path}'. Available keys: {available}"
                    )
            elif isinstance(curr, list) and token.isdigit():
                list_idx = int(token)
                if 0 <= list_idx < len(curr):
                    curr = curr[list_idx]
                else:
                    raise MappingResolutionError(
                        f"Index {list_idx} out of range (length {len(curr)}) along path '{path}'"
                    )
            else:
                raise MappingResolutionError(
                    f"Cannot navigate '{token}' on non-collection type '{type(curr).__name__}' along path '{path}'"
                )
        return curr

    if path.startswith("steps."):
        remainder = path[len("steps."):]
        tokens = remainder.split(".")
        if len(tokens) < 2:
            raise MappingResolutionError(
                f"Malformed step reference path '{path}'. Expected format 'steps.<step_id>.<property>'"
            )

        step_id = tokens[0]
        steps_ctx = context.get("steps", {})
        if step_id not in steps_ctx:
            available_steps = list(steps_ctx.keys())
            raise MappingResolutionError(
                f"Step '{step_id}' output is not available. Preceding executed steps: {available_steps}"
            )

        curr = steps_ctx[step_id]
        for token in tokens[1:]:
            if curr is None:
                raise MappingResolutionError(
                    f"Cannot access property '{token}' from null along path '{path}'"
                )
            if isinstance(curr, dict):
                if token in curr:
                    curr = curr[token]
                else:
                    available = list(curr.keys())
                    raise MappingResolutionError(
                        f"Field '{token}' not found in output of step '{step_id}'. Available keys: {available}"
                    )
            elif isinstance(curr, list) and token.isdigit():
                list_idx = int(token)
                if 0 <= list_idx < len(curr):
                    curr = curr[list_idx]
                else:
                    raise MappingResolutionError(
                        f"Index {list_idx} out of range (length {len(curr)}) along path '{path}'"
                    )
            else:
                raise MappingResolutionError(
                    f"Cannot navigate '{token}' on non-collection type '{type(curr).__name__}' along path '{path}'"
                )
        return curr

    # Static or literal string that does not target a dynamic context path
    return path


def resolve_value(val: Any, context: dict[str, Any]) -> Any:
    """Recursively resolves dynamic mapping paths inside arbitrary values, dictionaries, or lists."""
    if isinstance(val, str):
        if val.startswith("trigger.") or val.startswith("steps."):
            return resolve_path(val, context)
        return val
    elif isinstance(val, dict):
        return {k: resolve_value(v, context) for k, v in val.items()}
    elif isinstance(val, list):
        return [resolve_value(item, context) for item in val]
    return val


def resolve_mapping(mapping: dict[str, Any] | None, context: dict[str, Any]) -> dict[str, Any]:
    """
    Transforms field mapping definitions into concrete resolved runtime values.
    
    Example:
      mapping = {"name": "trigger.values.Name", "email": "trigger.values.Email", "source": "sme_connect"}
      context = {"trigger": {"values": {"Name": "Alice", "Email": "alice@corp.com"}}, "steps": {}}
      => {"name": "Alice", "email": "alice@corp.com", "source": "sme_connect"}
    """
    if not mapping:
        return {}
    return {k: resolve_value(v, context) for k, v in mapping.items()}
