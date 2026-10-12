from datetime import datetime
import re
from typing import Any

from app.modules.executions.resolver import resolve_path
from app.modules.transformations.schemas import TransformationCatalogItem, TransformationType

TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\.\-]+)\s*\}\}")


def extract_value(
    expr: Any,
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> Any:
    """
    Extracts a value from an expression:
    - If direct path string ('trigger.x' or 'steps.y.z'): resolves via resolve_path
    - If template string with '{{...}}': resolves via evaluate_template
    - If dict with 'transform': evaluates transformation recursively
    - Else: returns literal value
    """
    if isinstance(expr, str):
        if expr.startswith("trigger.") or expr.startswith("steps."):
            return resolve_path(expr, context, allowed_step_ids)
        elif "{{" in expr and "}}" in expr:
            return evaluate_template(expr, context, allowed_step_ids)
        return expr
    elif isinstance(expr, dict) and ("transform" in expr or "type" in expr):
        return evaluate_transformation(expr, context, allowed_step_ids)
    return expr


def evaluate_template(
    template_str: str,
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    """
    Evaluates template strings with interpolation, e.g.
    'Hello {{trigger.values.FirstName}} {{trigger.values.LastName}}!'
    """
    def _replacer(match: re.Match) -> str:
        var_path = match.group(1).strip()
        try:
            val = resolve_path(var_path, context, allowed_step_ids)
            return "" if val is None else str(val)
        except Exception:
            return ""

    return TEMPLATE_PATTERN.sub(_replacer, template_str)


# ============================================================================
# Individual Transformation Functions
# ============================================================================

def transform_concat(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    sources = params.get("sources", [])
    if not isinstance(sources, list):
        sources = [sources]
    separator = str(params.get("separator", ""))

    extracted_parts = []
    for s in sources:
        val = extract_value(s, context, allowed_step_ids)
        if val is not None:
            extracted_parts.append(str(val))
    return separator.join(extracted_parts)


def transform_trim(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    val = extract_value(params.get("source"), context, allowed_step_ids)
    return "" if val is None else str(val).strip()


def transform_uppercase(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    val = extract_value(params.get("source"), context, allowed_step_ids)
    return "" if val is None else str(val).upper()


def transform_lowercase(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    val = extract_value(params.get("source"), context, allowed_step_ids)
    return "" if val is None else str(val).lower()


def transform_titlecase(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    val = extract_value(params.get("source"), context, allowed_step_ids)
    return "" if val is None else str(val).title()


def transform_replace(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    val = extract_value(params.get("source"), context, allowed_step_ids)
    text = "" if val is None else str(val)
    find = str(params.get("find", ""))
    replace_with = str(params.get("replace_with", ""))
    if not find:
        return text
    return text.replace(find, replace_with)


def transform_substring(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    val = extract_value(params.get("source"), context, allowed_step_ids)
    text = "" if val is None else str(val)
    start = int(params.get("start", 0))
    end = params.get("end")
    if end is not None:
        return text[start:int(end)]
    length = params.get("length")
    if length is not None:
        return text[start:start + int(length)]
    return text[start:]


def transform_default_value(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> Any:
    default_val = params.get("default")
    try:
        val = extract_value(params.get("source"), context, allowed_step_ids)
        if val is None or val == "":
            return default_val
        return val
    except Exception:
        return default_val


def transform_to_string(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    default_val = params.get("default", "")
    try:
        val = extract_value(params.get("source"), context, allowed_step_ids)
        if val is None:
            return str(default_val)
        return str(val)
    except Exception:
        return str(default_val)


def transform_to_number(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> float:
    default_val = float(params.get("default", 0.0))
    try:
        val = extract_value(params.get("source"), context, allowed_step_ids)
        if val is None or val == "":
            return default_val
        if isinstance(val, (int, float)):
            return float(val)
        # Clean currency symbols, commas, or spaces from numeric string
        cleaned = re.sub(r"[^\d\.\-]", "", str(val))
        return float(cleaned) if cleaned else default_val
    except Exception:
        return default_val


def transform_to_integer(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> int:
    default_val = int(params.get("default", 0))
    try:
        val = extract_value(params.get("source"), context, allowed_step_ids)
        if val is None or val == "":
            return default_val
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(round(val))
        cleaned = re.sub(r"[^\d\.\-]", "", str(val))
        if "." in cleaned:
            return int(round(float(cleaned)))
        return int(cleaned) if cleaned else default_val
    except Exception:
        return default_val


def transform_to_boolean(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> bool:
    default_val = bool(params.get("default", False))
    try:
        val = extract_value(params.get("source"), context, allowed_step_ids)
        if val is None or val == "":
            return default_val
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return bool(val != 0)
        str_val = str(val).strip().lower()
        if str_val in ("true", "1", "yes", "y", "t", "on", "active"):
            return True
        if str_val in ("false", "0", "no", "n", "f", "off", "inactive"):
            return False
        return bool(val)
    except Exception:
        return default_val


def transform_format_date(
    params: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> str:
    output_format = str(params.get("output_format", "%Y-%m-%d"))
    input_format = params.get("input_format")
    default_val = params.get("default", "")

    try:
        val = extract_value(params.get("source"), context, allowed_step_ids)
        if not val:
            return str(default_val)

        dt = None
        if isinstance(val, datetime):
            dt = val
        elif isinstance(val, str):
            val_str = val.strip()
            if input_format:
                dt = datetime.strptime(val_str, input_format)
            else:
                # Common formats: ISO-8601, YYYY-MM-DD, etc.
                cleaned_iso = val_str.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(cleaned_iso)
                except ValueError:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                        try:
                            dt = datetime.strptime(val_str, fmt)
                            break
                        except ValueError:
                            pass

        if dt:
            return dt.strftime(output_format)
        return str(val)
    except Exception:
        return str(default_val)


TRANSFORM_HANDLERS = {
    TransformationType.CONCAT.value: transform_concat,
    TransformationType.TRIM.value: transform_trim,
    TransformationType.UPPERCASE.value: transform_uppercase,
    TransformationType.LOWERCASE.value: transform_lowercase,
    TransformationType.TITLECASE.value: transform_titlecase,
    TransformationType.REPLACE.value: transform_replace,
    TransformationType.SUBSTRING.value: transform_substring,
    TransformationType.DEFAULT_VALUE.value: transform_default_value,
    TransformationType.TO_STRING.value: transform_to_string,
    TransformationType.TO_NUMBER.value: transform_to_number,
    TransformationType.TO_INTEGER.value: transform_to_integer,
    TransformationType.TO_BOOLEAN.value: transform_to_boolean,
    TransformationType.FORMAT_DATE.value: transform_format_date,
}


def evaluate_transformation(
    transform_def: dict[str, Any],
    context: dict[str, Any],
    allowed_step_ids: set[str] | list[str] | None = None,
) -> Any:
    """
    Evaluates a structured transformation specification dictionary, e.g.:
    {
      "transform": "concat",
      "sources": ["trigger.values.FirstName", " ", "trigger.values.LastName"]
    }
    """
    tf_type = str(transform_def.get("transform") or transform_def.get("type", "")).lower()
    handler = TRANSFORM_HANDLERS.get(tf_type)
    if not handler:
        raise ValueError(
            f"Unsupported transformation type '{tf_type}'. "
            f"Supported transformations: {sorted(list(TRANSFORM_HANDLERS.keys()))}"
        )

    result = handler(transform_def, context, allowed_step_ids)

    # Optional modifiers chaining
    if transform_def.get("trim") is True and isinstance(result, str):
        result = result.strip()
    if transform_def.get("uppercase") is True and isinstance(result, str):
        result = result.upper()
    if transform_def.get("lowercase") is True and isinstance(result, str):
        result = result.lower()

    return result


def get_transformations_catalog() -> list[TransformationCatalogItem]:
    """Returns catalog of supported transformations and examples."""
    return [
        TransformationCatalogItem(
            type="concat",
            name="Concatenate Strings",
            description="Combines multiple text fields and literals with an optional separator.",
            category="text",
            parameters=[
                {"name": "sources", "type": "list[string]", "required": True, "description": "Ordered list of variables and strings to join"},
                {"name": "separator", "type": "string", "required": False, "description": "Optional delimiter between items (e.g. ' ' or '-')"},
            ],
            example={
                "transform": "concat",
                "sources": ["trigger.values.FirstName", " ", "trigger.values.LastName"],
            },
        ),
        TransformationCatalogItem(
            type="trim",
            name="Trim Whitespace",
            description="Removes leading and trailing whitespace from a text value.",
            category="text",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Field path or text"},
            ],
            example={"transform": "trim", "source": "trigger.values.Email"},
        ),
        TransformationCatalogItem(
            type="uppercase",
            name="Uppercase Text",
            description="Converts all characters in a text field to uppercase.",
            category="text",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Field path or text"},
            ],
            example={"transform": "uppercase", "source": "trigger.values.CountryCode"},
        ),
        TransformationCatalogItem(
            type="lowercase",
            name="Lowercase Text",
            description="Converts all characters in a text field to lowercase.",
            category="text",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Field path or text"},
            ],
            example={"transform": "lowercase", "source": "trigger.values.Email"},
        ),
        TransformationCatalogItem(
            type="titlecase",
            name="Title Case / Capitalize",
            description="Capitalizes the first character of each word in a string.",
            category="text",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Field path or text"},
            ],
            example={"transform": "titlecase", "source": "trigger.values.City"},
        ),
        TransformationCatalogItem(
            type="replace",
            name="Replace Substring",
            description="Replaces occurrences of a search string with a new value.",
            category="text",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Input text"},
                {"name": "find", "type": "string", "required": True, "description": "Substring to search for"},
                {"name": "replace_with", "type": "string", "required": False, "description": "Replacement string"},
            ],
            example={"transform": "replace", "source": "trigger.values.Phone", "find": "+91", "replace_with": ""},
        ),
        TransformationCatalogItem(
            type="substring",
            name="Extract Substring",
            description="Extracts a slice of text between start and end index.",
            category="text",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Input text"},
                {"name": "start", "type": "integer", "required": False, "description": "Starting character index (0-based)"},
                {"name": "end", "type": "integer", "required": False, "description": "Ending character index"},
            ],
            example={"transform": "substring", "source": "trigger.values.Code", "start": 0, "end": 4},
        ),
        TransformationCatalogItem(
            type="default_value",
            name="Default Fallback Value",
            description="Provides a fallback value if the source field is null, empty string, or missing.",
            category="utility",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Source field path"},
                {"name": "default", "type": "any", "required": True, "description": "Default value to return if empty"},
            ],
            example={"transform": "default_value", "source": "trigger.values.Phone", "default": "N/A"},
        ),
        TransformationCatalogItem(
            type="to_string",
            name="Convert to String",
            description="Coerces numeric, boolean, or object values into a string representation.",
            category="coercion",
            parameters=[
                {"name": "source", "type": "any", "required": True, "description": "Source value to coerce"},
            ],
            example={"transform": "to_string", "source": "trigger.values.PostalCode"},
        ),
        TransformationCatalogItem(
            type="to_number",
            name="Convert to Number (Float)",
            description="Parses currency or formatted string values into a numeric float.",
            category="coercion",
            parameters=[
                {"name": "source", "type": "any", "required": True, "description": "Source value to coerce"},
                {"name": "default", "type": "number", "required": False, "description": "Fallback value if parsing fails"},
            ],
            example={"transform": "to_number", "source": "trigger.values.Amount", "default": 0.0},
        ),
        TransformationCatalogItem(
            type="to_integer",
            name="Convert to Integer",
            description="Parses or rounds values into an integer.",
            category="coercion",
            parameters=[
                {"name": "source", "type": "any", "required": True, "description": "Source value to coerce"},
                {"name": "default", "type": "integer", "required": False, "description": "Fallback integer"},
            ],
            example={"transform": "to_integer", "source": "trigger.values.Quantity", "default": 1},
        ),
        TransformationCatalogItem(
            type="to_boolean",
            name="Convert to Boolean",
            description="Coerces truthy/falsy strings ('true', 'yes', '1') or numbers into a boolean.",
            category="coercion",
            parameters=[
                {"name": "source", "type": "any", "required": True, "description": "Source value to coerce"},
                {"name": "default", "type": "boolean", "required": False, "description": "Fallback boolean"},
            ],
            example={"transform": "to_boolean", "source": "trigger.values.IsSubscribed", "default": False},
        ),
        TransformationCatalogItem(
            type="format_date",
            name="Format Date & Time",
            description="Parses ISO timestamps or date strings into customized date formats.",
            category="date",
            parameters=[
                {"name": "source", "type": "string", "required": True, "description": "Source date/time value"},
                {"name": "output_format", "type": "string", "required": True, "description": "Output strftime format, e.g. '%Y-%m-%d'"},
                {"name": "input_format", "type": "string", "required": False, "description": "Optional explicit input format"},
            ],
            example={"transform": "format_date", "source": "trigger.created_at", "output_format": "%d-%m-%Y"},
        ),
    ]
