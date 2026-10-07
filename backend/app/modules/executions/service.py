from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

import json

from app.core.security import decrypt_credentials
from app.database.models import Connection, Workflow, WorkflowExecution, WorkflowStepExecution, WorkflowVersion
from app.modules.audit.service import create_audit_log
from app.modules.connectors.registry import get_adapter
from app.modules.executions.evaluator import evaluate_condition
from app.modules.executions.resolver import resolve_mapping, sanitize_data, sanitize_error_message
from app.modules.executions.retry_policy import (
    MAX_RETRY_COUNT,
    calculate_next_retry,
    classify_failure,
    explain_failure_for_user,
)
from app.modules.executions.safety_limits import (
    MAX_EXECUTION_DURATION_SECONDS,
    MAX_PAYLOAD_BYTES,
    MAX_WORKFLOW_STEPS,
)
from app.modules.executions.schemas import (
    ExecutionDetail,
    ExecutionSummary,
    StepExecutionResponse,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_step_response(step_exec: WorkflowStepExecution) -> StepExecutionResponse:
    return StepExecutionResponse(
        id=step_exec.id,
        execution_id=step_exec.execution_id,
        step_id=step_exec.step_id,
        step_index=step_exec.step_index,
        status=step_exec.status,
        failure_category=step_exec.failure_category,
        input_data=sanitize_data(step_exec.input_data or {}),
        output_data=sanitize_data(step_exec.output_data or {}),
        error_message=sanitize_error_message(step_exec.error_message),
        started_at=step_exec.started_at,
        completed_at=step_exec.completed_at,
        created_at=step_exec.created_at,
    )


def to_summary_response(execution: WorkflowExecution) -> ExecutionSummary:
    wf_name = execution.workflow.name if execution.workflow else None
    return ExecutionSummary(
        id=execution.id,
        workflow_id=execution.workflow_id,
        workflow_version_id=execution.workflow_version_id,
        workflow_name=wf_name,
        organization_id=execution.organization_id,
        status=execution.status,
        attempt_number=execution.attempt_number,
        retry_count=execution.retry_count,
        retry_of_execution_id=execution.retry_of_execution_id,
        next_retry_at=execution.next_retry_at,
        failure_category=execution.failure_category,
        last_error_at=execution.last_error_at,
        trigger_data=sanitize_data(execution.trigger_data or {}),
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error_message=sanitize_error_message(execution.error_message),
        created_at=execution.created_at,
    )


def to_detail_response(execution: WorkflowExecution) -> ExecutionDetail:
    wf_name = execution.workflow.name if execution.workflow else None
    steps = [to_step_response(s) for s in sorted(execution.step_executions, key=lambda x: x.step_index)]

    failure_title = None
    failure_explanation = None
    actionable_guidance = None
    can_manual_retry = False

    if execution.status == "failed":
        exp = explain_failure_for_user(
            failure_category=execution.failure_category,
            error_message=execution.error_message,
            will_retry=bool(execution.next_retry_at),
            next_retry_at=execution.next_retry_at,
        )
        failure_title = exp["title"]
        failure_explanation = exp["explanation"]
        actionable_guidance = exp["guidance"]
        can_manual_retry = exp["can_manual_retry"]

    return ExecutionDetail(
        id=execution.id,
        workflow_id=execution.workflow_id,
        workflow_version_id=execution.workflow_version_id,
        workflow_name=wf_name,
        organization_id=execution.organization_id,
        status=execution.status,
        attempt_number=execution.attempt_number,
        retry_count=execution.retry_count,
        retry_of_execution_id=execution.retry_of_execution_id,
        next_retry_at=execution.next_retry_at,
        failure_category=execution.failure_category,
        last_error_at=execution.last_error_at,
        trigger_data=sanitize_data(execution.trigger_data or {}),
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error_message=sanitize_error_message(execution.error_message),
        created_at=execution.created_at,
        steps=steps,
        failure_title=failure_title,
        failure_explanation=failure_explanation,
        actionable_guidance=actionable_guidance,
        can_manual_retry=can_manual_retry,
    )


def get_execution(
    db: Session,
    execution_id: int,
    organization_id: int | None = None,
) -> WorkflowExecution:
    query = (
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.step_executions),
            selectinload(WorkflowExecution.workflow),
            selectinload(WorkflowExecution.workflow_version),
        )
        .where(WorkflowExecution.id == execution_id)
    )
    if organization_id is not None:
        query = query.where(WorkflowExecution.organization_id == organization_id)

    execution = db.scalar(query)
    if not execution:
        raise ValueError("Execution not found")
    return execution


def list_executions(
    db: Session,
    organization_id: int | None = None,
    workflow_id: int | None = None,
    status: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkflowExecution]:
    query = (
        select(WorkflowExecution)
        .options(
            selectinload(WorkflowExecution.workflow),
            selectinload(WorkflowExecution.step_executions),
        )
        .order_by(WorkflowExecution.id.desc())
    )
    if organization_id is not None:
        query = query.where(WorkflowExecution.organization_id == organization_id)
    if workflow_id is not None:
        query = query.where(WorkflowExecution.workflow_id == workflow_id)
    if status is not None:
        query = query.where(WorkflowExecution.status == status)
    if from_date is not None:
        query = query.where(WorkflowExecution.created_at >= from_date)
    if to_date is not None:
        query = query.where(WorkflowExecution.created_at <= to_date)

    return list(db.scalars(query.offset(offset).limit(limit)).all())


def execute_workflow(
    db: Session,
    workflow_id: int,
    trigger_data: dict[str, Any],
    organization_id: int | None = None,
    attempt_number: int = 1,
    retry_count: int = 0,
    retry_of_execution_id: int | None = None,
    workflow_version_id: int | None = None,
    cached_step_outputs: dict[str, dict[str, Any]] | None = None,
    cached_step_inputs: dict[str, dict[str, Any]] | None = None,
) -> WorkflowExecution:
    """
    Executes a published workflow in a connector-agnostic manner.
    Guarantees:
      1. Resolves workflow and verifies organization ownership.
      2. Validates workflow status is 'published' (rejects drafts and paused).
      3. Resolves published version and consumes its immutable definition.
      4. Records WorkflowExecution and sequential WorkflowStepExecution records.
      5. Decrypts credentials in-memory only; never logs or persists credentials.
      6. Evaluates DAG mappings and conditions dynamically.
      7. Delegates external API calls exclusively to connector adapters.
    """
    # 1. Resolve workflow
    query = select(Workflow).where(Workflow.id == workflow_id)
    if organization_id is not None:
        query = query.where(Workflow.organization_id == organization_id)

    workflow = db.scalar(query)
    if not workflow:
        raise ValueError("Workflow not found")

    # 2. Check workflow status
    if workflow.status != "published":
        raise ValueError(
            f"Cannot execute workflow with status '{workflow.status}'. Workflow must be 'published'."
        )

    # 3. Resolve published version (immutable)
    if workflow_version_id is not None:
        published_version = db.scalar(
            select(WorkflowVersion).where(
                WorkflowVersion.id == workflow_version_id,
                WorkflowVersion.workflow_id == workflow.id,
                WorkflowVersion.published_at.is_not(None),
            )
        )
        if not published_version:
            raise ValueError(
                f"Workflow version {workflow_version_id} not found or not published for workflow {workflow_id}"
            )
    else:
        published_version = db.scalar(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_id == workflow.id,
                WorkflowVersion.published_at.is_not(None),
            )
            .order_by(WorkflowVersion.version_number.desc())
        )
        if not published_version:
            raise ValueError("No published version found for this workflow")

    definition = published_version.definition or {}
    steps = definition.get("steps", [])

    # Enforce payload size safety limit (Module 6.10)
    try:
        payload_bytes = len(json.dumps(trigger_data or {}, default=str).encode("utf-8"))
    except Exception:
        payload_bytes = 0
    if payload_bytes > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"Trigger payload exceeds maximum permitted safety limit of {MAX_PAYLOAD_BYTES // 1000} KB"
        )

    # Enforce step count safety limit (Module 6.10)
    if len(steps) > MAX_WORKFLOW_STEPS:
        raise ValueError(
            f"Workflow definition exceeds maximum permitted safety limit of {MAX_WORKFLOW_STEPS} steps"
        )

    # 4. Create WorkflowExecution
    now = _utc_now()
    execution = WorkflowExecution(
        workflow_id=workflow.id,
        workflow_version_id=published_version.id,
        organization_id=workflow.organization_id,
        status="running",
        trigger_data=sanitize_data(trigger_data or {}),
        attempt_number=attempt_number,
        retry_count=retry_count,
        retry_of_execution_id=retry_of_execution_id,
        started_at=now,
        created_at=now,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    # 5. Runtime context initialization
    context: dict[str, Any] = {
        "trigger": trigger_data or {},
        "steps": {},
    }
    executed_step_ids: set[str] = set()
    is_skipping = False
    skip_reason: str | None = None
    cached_step_outputs = cached_step_outputs or {}
    cached_step_inputs = cached_step_inputs or {}

    # 6. Execute steps sequentially
    for idx, step_def in enumerate(steps):
        step_id = step_def.get("id", f"step_{idx + 1}")
        step_type = step_def.get("type", "action")
        step_start_time = _utc_now()

        # Enforce execution duration timeout limit (Module 6.10)
        started_at = execution.started_at
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = (_utc_now() - started_at).total_seconds() if started_at else 0
        if elapsed_seconds > MAX_EXECUTION_DURATION_SECONDS:
            fail_time = _utc_now()
            execution.status = "failed"
            execution.failure_category = "timeout"
            execution.last_error_at = fail_time
            execution.next_retry_at = None
            execution.error_message = (
                f"Execution aborted: exceeded maximum allowed duration limit of {MAX_EXECUTION_DURATION_SECONDS} seconds"
            )
            execution.completed_at = fail_time
            db.commit()
            db.refresh(execution)
            try:
                create_audit_log(
                    db=db,
                    organization_id=execution.organization_id,
                    user_id=workflow.created_by,
                    action="WORKFLOW_EXECUTION_FAILED",
                    resource_type="workflow_execution",
                    resource_id=execution.id,
                    details="Timeout: exceeded maximum execution duration",
                )
            except Exception:
                pass
            return execution

        # Step resume optimization: reuse verified successful outputs from prior attempt to avoid repeating side effects
        if step_id in cached_step_outputs:
            cached_out = cached_step_outputs[step_id]
            cached_in = cached_step_inputs.get(step_id, {})
            step_exec = WorkflowStepExecution(
                execution_id=execution.id,
                step_id=step_id,
                step_index=idx,
                status="success",
                input_data=cached_in,
                output_data=cached_out,
                started_at=step_start_time,
                completed_at=step_start_time,
                created_at=step_start_time,
            )
            db.add(step_exec)
            context["steps"][step_id] = cached_out
            executed_step_ids.add(step_id)
            continue

        if is_skipping:
            # Step skipped due to prior condition evaluating to False
            step_exec = WorkflowStepExecution(
                execution_id=execution.id,
                step_id=step_id,
                step_index=idx,
                status="skipped",
                input_data={},
                output_data={"skipped": True, "reason": skip_reason or "Prior condition evaluated to false"},
                started_at=None,
                completed_at=None,
                created_at=step_start_time,
            )
            db.add(step_exec)
            continue

        step_exec = WorkflowStepExecution(
            execution_id=execution.id,
            step_id=step_id,
            step_index=idx,
            status="running",
            input_data={},
            output_data={},
            started_at=step_start_time,
            created_at=step_start_time,
        )
        db.add(step_exec)
        db.flush()

        # Handle condition step
        if step_type == "condition":
            field_expr = step_def.get("field", "")
            operator = step_def.get("operator", "equals")
            expected_val = step_def.get("value")

            try:
                condition_result = evaluate_condition(
                    field_expr=field_expr,
                    operator=operator,
                    expected_value=expected_val,
                    context=context,
                    allowed_step_ids=executed_step_ids,
                )
                step_exec.status = "success"
                step_exec.input_data = {
                    "field": field_expr,
                    "operator": operator,
                    "expected_value": expected_val,
                }
                step_exec.output_data = {
                    "condition_met": condition_result,
                }
                step_exec.completed_at = _utc_now()
                context["steps"][step_id] = step_exec.output_data
                executed_step_ids.add(step_id)

                if not condition_result:
                    is_skipping = True
                    skip_reason = f"Condition '{field_expr} {operator}' evaluated to false"

            except Exception as exc:
                clean_err = sanitize_error_message(str(exc))
                cat, retryable = classify_failure(exc)
                fail_time = _utc_now()

                step_exec.status = "failed"
                step_exec.failure_category = cat.value
                step_exec.error_message = clean_err
                step_exec.completed_at = fail_time

                execution.status = "failed"
                execution.failure_category = cat.value
                execution.last_error_at = fail_time
                if retryable and execution.retry_count < MAX_RETRY_COUNT:
                    execution.next_retry_at = calculate_next_retry(execution.retry_count, fail_time)
                else:
                    execution.next_retry_at = None

                execution.error_message = f"Condition step '{step_id}' error: {clean_err}"
                execution.completed_at = fail_time
                db.commit()
                db.refresh(execution)
                try:
                    action_name = "WORKFLOW_RETRY_SCHEDULED" if execution.next_retry_at else "WORKFLOW_EXECUTION_FAILED"
                    create_audit_log(
                        db=db,
                        organization_id=execution.organization_id,
                        user_id=workflow.created_by,
                        action=action_name,
                        resource_type="workflow_execution",
                        resource_id=execution.id,
                        details=f"Condition step '{step_id}' failed: {clean_err[:150]}",
                    )
                except Exception:
                    pass
                return execution

        # Handle action step
        elif step_type == "action":
            connector_slug = step_def.get("connector", "")
            action_slug = step_def.get("action", "")
            step_config = step_def.get("config", {})
            raw_mapping = step_def.get("mapping", {})

            try:
                # Resolve field mappings
                resolved_mapping = resolve_mapping(
                    mapping=raw_mapping,
                    context=context,
                    allowed_step_ids=executed_step_ids,
                )
                resolved_input = dict(step_config)
                resolved_input.update(resolved_mapping)
                step_exec.input_data = sanitize_data(resolved_input)

                # Resolve connector adapter
                adapter = get_adapter(connector_slug)
                if not adapter:
                    raise ValueError(f"Unknown connector '{connector_slug}'")

                # Resolve active connection
                connection = db.scalar(
                    select(Connection).where(
                        Connection.organization_id == workflow.organization_id,
                        Connection.connector_slug == connector_slug,
                        Connection.status == "active",
                    )
                )
                if not connection:
                    raise ValueError(
                        f"No active connection found for connector '{connector_slug}' in this organization"
                    )

                # Decrypt credentials in memory only
                creds = decrypt_credentials(connection.credentials)

                # Merge connection config and step config
                runtime_config = dict(connection.config or {})
                runtime_config.update(step_config)

                # Delegate to connector adapter
                action_result = adapter.execute_action(
                    action_slug=action_slug,
                    input_data=resolved_input,
                    config=runtime_config,
                    credentials=creds,
                )
                del creds  # Clean sensitive credentials from scope

                sanitized_output = sanitize_data(action_result)
                step_exec.output_data = sanitized_output
                step_exec.status = "success"
                step_exec.completed_at = _utc_now()

                context["steps"][step_id] = sanitized_output
                executed_step_ids.add(step_id)

            except Exception as exc:
                clean_err = sanitize_error_message(str(exc))
                cat, retryable = classify_failure(exc)
                fail_time = _utc_now()

                step_exec.status = "failed"
                step_exec.failure_category = cat.value
                step_exec.error_message = clean_err
                step_exec.completed_at = fail_time

                execution.status = "failed"
                execution.failure_category = cat.value
                execution.last_error_at = fail_time
                if retryable and execution.retry_count < MAX_RETRY_COUNT:
                    execution.next_retry_at = calculate_next_retry(execution.retry_count, fail_time)
                else:
                    execution.next_retry_at = None

                execution.error_message = f"Step '{step_id}' failed: {clean_err}"
                execution.completed_at = fail_time
                db.commit()
                db.refresh(execution)
                try:
                    action_name = "WORKFLOW_RETRY_SCHEDULED" if execution.next_retry_at else "WORKFLOW_EXECUTION_FAILED"
                    create_audit_log(
                        db=db,
                        organization_id=execution.organization_id,
                        user_id=workflow.created_by,
                        action=action_name,
                        resource_type="workflow_execution",
                        resource_id=execution.id,
                        details=f"Step '{step_id}' failed ({execution.failure_category}): {clean_err[:150]}",
                    )
                except Exception:
                    pass
                return execution

    # All steps completed
    execution.status = "success"
    execution.completed_at = _utc_now()
    db.commit()
    db.refresh(execution)
    try:
        create_audit_log(
            db=db,
            organization_id=execution.organization_id,
            user_id=workflow.created_by,
            action="WORKFLOW_EXECUTION_SUCCEEDED",
            resource_type="workflow_execution",
            resource_id=execution.id,
            details=f"Execution completed successfully for workflow '{workflow.name}'",
        )
    except Exception:
        pass
    return execution


def retry_execution(
    db: Session,
    execution_id: int,
    organization_id: int | None = None,
) -> WorkflowExecution:
    """
    Safely retries a failed execution (Module 6.2):
      - Validates original execution exists, belongs to organization, and status == 'failed'.
      - Validates workflow is still published (rejects if paused or draft).
      - Pinpoints the EXACT historical WorkflowVersion executed previously.
      - Reuses successful preceding step outputs to avoid re-running side effects.
      - Increments attempt_number and retry_count.
      - Links retry_of_execution_id to original execution.
      - Clears next_retry_at on the original execution.
    """
    orig_exec = get_execution(db, execution_id, organization_id=organization_id)
    if orig_exec.status != "failed":
        raise ValueError(
            f"Cannot retry execution with status '{orig_exec.status}'. Only failed executions can be retried."
        )

    workflow = orig_exec.workflow
    if not workflow:
        workflow = db.scalar(select(Workflow).where(Workflow.id == orig_exec.workflow_id))
    else:
        db.refresh(workflow)
    if not workflow or workflow.status != "published":
        raise ValueError("Cannot retry execution: Workflow is not published or is paused.")

    # Collect successful steps to avoid duplicating side effects
    cached_step_outputs: dict[str, dict[str, Any]] = {}
    cached_step_inputs: dict[str, dict[str, Any]] = {}
    for step in sorted(orig_exec.step_executions, key=lambda s: s.step_index):
        if step.status == "success":
            cached_step_outputs[step.step_id] = step.output_data or {}
            cached_step_inputs[step.step_id] = step.input_data or {}
        else:
            # First non-success step encountered (failed/pending): stop caching
            break

    # Clear next_retry_at on original execution so it won't be retried again
    orig_exec.next_retry_at = None
    db.commit()

    # Execute retry referencing the EXACT original workflow_version_id
    new_execution = execute_workflow(
        db=db,
        workflow_id=orig_exec.workflow_id,
        trigger_data=orig_exec.trigger_data or {},
        organization_id=orig_exec.organization_id,
        attempt_number=orig_exec.attempt_number + 1,
        retry_count=orig_exec.retry_count + 1,
        retry_of_execution_id=orig_exec.id,
        workflow_version_id=orig_exec.workflow_version_id,
        cached_step_outputs=cached_step_outputs,
        cached_step_inputs=cached_step_inputs,
    )
    try:
        create_audit_log(
            db=db,
            organization_id=orig_exec.organization_id,
            user_id=workflow.created_by,
            action="WORKFLOW_EXECUTION_RETRIED",
            resource_type="workflow_execution",
            resource_id=new_execution.id,
            details=f"Retried execution {orig_exec.id}",
        )
    except Exception:
        pass
    return new_execution


def run_retry_cycle(db: Session, limit: int = 50) -> list[WorkflowExecution]:
    """
    Background worker cycle: Finds failed executions whose next_retry_at is due
    and safely executes retries (Module 6.2).
    """
    now = _utc_now()
    due_query = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.status == "failed",
            WorkflowExecution.next_retry_at.is_not(None),
            WorkflowExecution.next_retry_at <= now,
            WorkflowExecution.retry_count < MAX_RETRY_COUNT,
        )
        .order_by(WorkflowExecution.next_retry_at.asc())
        .limit(limit)
    )
    due_executions = list(db.scalars(due_query).all())
    retried_list: list[WorkflowExecution] = []
    for due_exec in due_executions:
        try:
            retried = retry_execution(db, due_exec.id, organization_id=due_exec.organization_id)
            retried_list.append(retried)
        except Exception:
            # If retry fails to initiate (e.g. workflow was paused or deleted), clear next_retry_at
            due_exec.next_retry_at = None
            db.commit()
    return retried_list
