import re
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ValidationError

from app.modules.connectors.registry import get_adapter
from app.modules.workflows.schemas import (
    ActionStepDefinition,
    ConditionOperator,
    ConditionStepDefinition,
    ValidationErrorItem,
    ValidationResult,
    WorkflowDefinition,
)

STEP_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
VALID_SCHEDULE_FREQUENCIES = {"hourly", "daily", "weekly"}
VALID_DAYS_OF_WEEK = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}


def validate_schedule_config(config: dict[str, Any]) -> list[ValidationErrorItem]:
    errs: list[ValidationErrorItem] = []
    if not isinstance(config, dict):
        errs.append(
            ValidationErrorItem(
                path="trigger.config",
                message="Schedule config must be an object",
                code="INVALID_SCHEDULE_CONFIG",
            )
        )
        return errs

    # Frequency check
    frequency = str(config.get("frequency", "")).lower()
    if not frequency or frequency not in VALID_SCHEDULE_FREQUENCIES:
        errs.append(
            ValidationErrorItem(
                path="trigger.config.frequency",
                message=f"Schedule frequency must be one of {sorted(list(VALID_SCHEDULE_FREQUENCIES))}",
                code="INVALID_FREQUENCY",
            )
        )

    # Timezone check
    tz_str = config.get("timezone")
    if not tz_str:
        errs.append(
            ValidationErrorItem(
                path="trigger.config.timezone",
                message="Schedule timezone is required (e.g. 'Asia/Kolkata', 'UTC')",
                code="MISSING_TIMEZONE",
            )
        )
    else:
        try:
            ZoneInfo(str(tz_str))
        except (ZoneInfoNotFoundError, ValueError, Exception):
            errs.append(
                ValidationErrorItem(
                    path="trigger.config.timezone",
                    message=f"Invalid IANA timezone '{tz_str}'",
                    code="INVALID_TIMEZONE",
                )
            )

    # Time check (daily & weekly)
    if frequency in ("daily", "weekly"):
        time_str = config.get("time")
        if not time_str or not isinstance(time_str, str):
            errs.append(
                ValidationErrorItem(
                    path="trigger.config.time",
                    message="Schedule 'time' is required in 'HH:MM' 24-hour format for daily/weekly schedules",
                    code="MISSING_TIME",
                )
            )
        else:
            time_parts = time_str.split(":")
            if (
                len(time_parts) != 2
                or not time_parts[0].isdigit()
                or not time_parts[1].isdigit()
                or not (0 <= int(time_parts[0]) <= 23)
                or not (0 <= int(time_parts[1]) <= 59)
            ):
                errs.append(
                    ValidationErrorItem(
                        path="trigger.config.time",
                        message=f"Schedule time '{time_str}' must be in valid 'HH:MM' 24-hour format (00:00 to 23:59)",
                        code="INVALID_TIME",
                    )
                )

    # Day of week check (weekly)
    if frequency == "weekly":
        dow = config.get("day_of_week")
        if dow is None:
            errs.append(
                ValidationErrorItem(
                    path="trigger.config.day_of_week",
                    message="Schedule 'day_of_week' is required for weekly schedules (e.g. 'monday', 'friday')",
                    code="MISSING_DAY_OF_WEEK",
                )
            )
        elif str(dow).lower() not in VALID_DAYS_OF_WEEK and not (isinstance(dow, int) and 0 <= dow <= 6):
            errs.append(
                ValidationErrorItem(
                    path="trigger.config.day_of_week",
                    message=f"Invalid day_of_week '{dow}'. Must be one of {sorted(list(VALID_DAYS_OF_WEEK))}",
                    code="INVALID_DAY_OF_WEEK",
                )
            )

    # Minute check (hourly)
    if frequency == "hourly" and "minute" in config:
        minute_val = config.get("minute")
        if not isinstance(minute_val, int) or not (0 <= minute_val <= 59):
            errs.append(
                ValidationErrorItem(
                    path="trigger.config.minute",
                    message=f"Schedule minute '{minute_val}' must be an integer between 0 and 59",
                    code="INVALID_MINUTE",
                )
            )

    return errs


class WorkflowValidationError(ValueError):
    """Raised when a workflow definition fails semantic or structural validation."""

    def __init__(self, errors: list[ValidationErrorItem]):
        self.errors = errors
        messages = [f"{e.path}: {e.message}" for e in errors]
        super().__init__("; ".join(messages))


def _extract_pydantic_errors(exc: ValidationError) -> list[ValidationErrorItem]:
    items: list[ValidationErrorItem] = []
    for error in exc.errors():
        loc = ".".join(str(elem) for elem in error["loc"])
        items.append(
            ValidationErrorItem(
                path=loc,
                message=error["msg"],
                code=error["type"],
            )
        )
    return items


def validate_workflow_definition(definition_data: WorkflowDefinition | dict[str, Any]) -> ValidationResult:
    """
    Validates a workflow definition without hardcoding any connector slugs.
    Enforces:
      1. Schema structure (Pydantic models)
      2. Step ID uniqueness and naming
      3. Dynamic capability resolution via ConnectorRegistry or Schedule trigger
      4. DAG mapping data flow (no forward or circular references)
      5. Condition operators and field sources
    """
    errors: list[ValidationErrorItem] = []

    # 1. Structural parse
    if isinstance(definition_data, WorkflowDefinition):
        wf = definition_data
    else:
        try:
            wf = WorkflowDefinition.model_validate(definition_data)
        except ValidationError as exc:
            return ValidationResult(valid=False, errors=_extract_pydantic_errors(exc))

    # 2. Validate trigger capability (Schedule or Connector)
    trigger = wf.trigger
    is_schedule = (trigger.type == "schedule") or (trigger.connector == "schedule")
    if is_schedule:
        errors.extend(validate_schedule_config(trigger.config))
    else:
        if not trigger.connector:
            errors.append(
                ValidationErrorItem(
                    path="trigger.connector",
                    message="Connector slug is required for connector triggers",
                    code="REQUIRED_CONNECTOR",
                )
            )
        else:
            trigger_adapter = get_adapter(trigger.connector)
            if not trigger_adapter:
                errors.append(
                    ValidationErrorItem(
                        path="trigger.connector",
                        message=f"Unknown connector '{trigger.connector}'",
                        code="UNKNOWN_CONNECTOR",
                    )
                )
            else:
                supported_triggers = [t["slug"] for t in trigger_adapter.supported_triggers]
                if trigger.event not in supported_triggers:
                    errors.append(
                        ValidationErrorItem(
                            path="trigger.event",
                            message=(
                                f"Trigger '{trigger.event}' is not supported by connector '{trigger.connector}'. "
                                f"Supported triggers: {supported_triggers}"
                            ),
                            code="UNSUPPORTED_TRIGGER",
                        )
                    )

    # 3. Validate steps, step count limit, capabilities, and mappings
    from app.modules.executions.safety_limits import MAX_WORKFLOW_STEPS
    if len(wf.steps) > MAX_WORKFLOW_STEPS:
        errors.append(
            ValidationErrorItem(
                path="steps",
                message=f"Workflow exceeds maximum allowed steps ({MAX_WORKFLOW_STEPS}). Current steps: {len(wf.steps)}",
                code="EXCEEDS_MAX_STEPS",
            )
        )

    seen_step_ids: set[str] = set()

    for idx, step in enumerate(wf.steps):
        step_path = f"steps[{idx}]"

        # Validate step ID syntax
        if not STEP_ID_PATTERN.match(step.id):
            errors.append(
                ValidationErrorItem(
                    path=f"{step_path}.id",
                    message=f"Step ID '{step.id}' must be alphanumeric and may include '-' or '_'",
                    code="INVALID_STEP_ID_FORMAT",
                )
            )

        # Validate step ID uniqueness
        if step.id in seen_step_ids:
            errors.append(
                ValidationErrorItem(
                    path=f"{step_path}.id",
                    message=f"Duplicate step ID '{step.id}' detected in workflow",
                    code="DUPLICATE_STEP_ID",
                )
            )

        # Validate by step type
        if isinstance(step, ActionStepDefinition):
            # Dynamic action capability resolution
            action_adapter = get_adapter(step.connector)
            if not action_adapter:
                errors.append(
                    ValidationErrorItem(
                        path=f"{step_path}.connector",
                        message=f"Unknown connector '{step.connector}' in step '{step.id}'",
                        code="UNKNOWN_CONNECTOR",
                    )
                )
            else:
                supported_actions = [a["slug"] for a in action_adapter.supported_actions]
                if step.action not in supported_actions:
                    errors.append(
                        ValidationErrorItem(
                            path=f"{step_path}.action",
                            message=(
                                f"Action '{step.action}' is not supported by connector '{step.connector}'. "
                                f"Supported actions: {supported_actions}"
                            ),
                            code="UNSUPPORTED_ACTION",
                        )
                    )

            # Validate mappings (DAG data flow)
            for target_field, source_expr in (step.mapping or {}).items():
                if isinstance(source_expr, str):
                    if source_expr.startswith("trigger."):
                        # Valid reference to workflow entry-point trigger
                        parts = source_expr.split(".", 1)
                        if len(parts) < 2 or not parts[1].strip():
                            errors.append(
                                ValidationErrorItem(
                                    path=f"{step_path}.mapping.{target_field}",
                                    message=f"Mapping source expression '{source_expr}' must specify a sub-property after 'trigger.'",
                                    code="MALFORMED_MAPPING_PATH",
                                )
                            )
                    elif source_expr.startswith("steps."):
                        parts = source_expr.split(".")
                        if len(parts) < 3:
                            errors.append(
                                ValidationErrorItem(
                                    path=f"{step_path}.mapping.{target_field}",
                                    message=f"Mapping source expression '{source_expr}' must follow format 'steps.<step_id>.<property>'",
                                    code="MALFORMED_MAPPING_PATH",
                                )
                            )
                        else:
                            ref_step_id = parts[1]
                            if ref_step_id == step.id:
                                errors.append(
                                    ValidationErrorItem(
                                        path=f"{step_path}.mapping.{target_field}",
                                        message=f"Step '{step.id}' cannot reference its own output in mapping",
                                        code="SELF_REFERENCE_MAPPING",
                                    )
                                )
                            elif ref_step_id not in seen_step_ids:
                                errors.append(
                                    ValidationErrorItem(
                                        path=f"{step_path}.mapping.{target_field}",
                                        message=(
                                            f"Step '{step.id}' references step '{ref_step_id}' which does not precede it. "
                                            f"Available preceding steps: {sorted(list(seen_step_ids)) or ['none']}"
                                        ),
                                        code="INVALID_STEP_REFERENCE",
                                    )
                                )

        elif isinstance(step, ConditionStepDefinition):
            # Validate condition field source reference
            field_expr = step.field
            if field_expr.startswith("trigger."):
                parts = field_expr.split(".", 1)
                if len(parts) < 2 or not parts[1].strip():
                    errors.append(
                        ValidationErrorItem(
                            path=f"{step_path}.field",
                            message=f"Condition field expression '{field_expr}' must specify a sub-property after 'trigger.'",
                            code="MALFORMED_CONDITION_PATH",
                        )
                    )
            elif field_expr.startswith("steps."):
                parts = field_expr.split(".")
                if len(parts) < 3 or not parts[2].strip():
                    errors.append(
                        ValidationErrorItem(
                            path=f"{step_path}.field",
                            message=f"Condition field expression '{field_expr}' must follow format 'steps.<step_id>.<property>'",
                            code="MALFORMED_CONDITION_PATH",
                        )
                    )
                else:
                    ref_step_id = parts[1]
                    if ref_step_id == step.id:
                        errors.append(
                            ValidationErrorItem(
                                path=f"{step_path}.field",
                                message=f"Condition step '{step.id}' cannot reference its own output",
                                code="SELF_REFERENCE_CONDITION",
                            )
                        )
                    elif ref_step_id not in seen_step_ids:
                        errors.append(
                            ValidationErrorItem(
                                path=f"{step_path}.field",
                                message=(
                                    f"Condition step '{step.id}' references step '{ref_step_id}' which does not precede it. "
                                    f"Available preceding steps: {sorted(list(seen_step_ids)) or ['none']}"
                                ),
                                code="INVALID_STEP_REFERENCE",
                            )
                        )
            else:
                errors.append(
                    ValidationErrorItem(
                        path=f"{step_path}.field",
                        message=f"Condition field '{field_expr}' must reference 'trigger.<property>' or 'steps.<step_id>.<property>'",
                        code="MALFORMED_CONDITION_PATH",
                    )
                )

            # Unary operators require NO value, binary operators require a comparison value
            if step.operator not in (ConditionOperator.IS_EMPTY, ConditionOperator.IS_NOT_EMPTY):
                if step.value is None:
                    errors.append(
                        ValidationErrorItem(
                            path=f"{step_path}.value",
                            message=f"Operator '{step.operator.value}' requires a comparison value",
                            code="MISSING_CONDITION_VALUE",
                        )
                    )

        seen_step_ids.add(step.id)

    return ValidationResult(valid=len(errors) == 0, errors=errors)


def validate_workflow_or_raise(definition_data: WorkflowDefinition | dict[str, Any]) -> WorkflowDefinition:
    """Validates the workflow definition and raises WorkflowValidationError on error."""
    result = validate_workflow_definition(definition_data)
    if not result.valid:
        raise WorkflowValidationError(result.errors)

    if isinstance(definition_data, WorkflowDefinition):
        return definition_data
    return WorkflowDefinition.model_validate(definition_data)
