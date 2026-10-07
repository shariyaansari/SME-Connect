import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.security import decrypt_credentials
from app.database.models import Connection, Membership, Workflow, WorkflowExecution, WorkflowStepExecution, WorkflowVersion
from app.modules.connectors.adapters.base import ConnectorExecutionError
from app.modules.connectors.registry import get_adapter
from app.modules.workflows.conditions import evaluate_condition_step
from app.modules.workflows.mapping import MappingResolutionError, resolve_mapping
from app.modules.workflows.retry_policy import evaluate_retry
from app.modules.workflows.schemas import (
    ActionStepDefinition,
    ConditionStepDefinition,
    ExecutionDetail,
    ExecutionSummary,
    StepExecutionResponse,
    WorkflowDefinition,
)

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "private_key",
    "credential",
    "_encrypted",
)

MAX_WORKFLOW_STEPS: int = 50
MAX_PAYLOAD_SIZE: int = 1_000_000  # 1MB safety ceiling


def _sanitize_payload(data: Any) -> Any:
    """
    Recursively scrubs known credential and secret keys from recorded payloads,
    guaranteeing secrets never leak into execution logs, records, or responses.
    """
    if isinstance(data, dict):
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_KEY_SUBSTRINGS):
                sanitized[k] = "••••••••"
            else:
                sanitized[k] = _sanitize_payload(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_payload(item) for item in data]
    return data


def _get_membership(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> Membership:
    query = select(Membership).where(Membership.user_id == user_id)
    if organization_id is not None:
        query = query.where(Membership.organization_id == organization_id)

    membership = db.scalar(query.order_by(Membership.id))
    if not membership:
        raise ValueError("User does not belong to the specified organization")
    return membership


def to_execution_summary(execution: WorkflowExecution) -> ExecutionSummary:
    """Converts a WorkflowExecution database entity to ExecutionSummary schema."""
    duration_ms: float | None = None
    if execution.started_at and execution.completed_at:
        duration_ms = round((execution.completed_at - execution.started_at).total_seconds() * 1000, 2)

    workflow_name = execution.workflow.name if execution.workflow else None
    version_number = execution.version.version_number if execution.version else None
    step_count = len(execution.step_executions) if execution.step_executions is not None else 0

    return ExecutionSummary(
        id=execution.id,
        workflow_id=execution.workflow_id,
        workflow_name=workflow_name,
        workflow_version_id=execution.workflow_version_id,
        version_number=version_number,
        organization_id=execution.organization_id,
        status=execution.status,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=duration_ms,
        error_message=execution.error_message,
        failure_category=execution.failure_category,
        attempt_number=execution.attempt_number,
        retry_of_execution_id=execution.retry_of_execution_id,
        retry_count=execution.retry_count,
        next_retry_at=execution.next_retry_at,
        last_error_at=execution.last_error_at,
        step_count=step_count,
        created_at=execution.created_at,
    )


def to_execution_detail(execution: WorkflowExecution) -> ExecutionDetail:
    """Converts a WorkflowExecution database entity to ExecutionDetail schema with enriched step metadata."""
    step_definitions_by_id: dict[str, dict[str, Any]] = {}
    if execution.version and execution.version.definition:
        try:
            raw_steps = execution.version.definition.get("steps", [])
            for s_def in raw_steps:
                if isinstance(s_def, dict) and "id" in s_def:
                    step_definitions_by_id[s_def["id"]] = s_def
        except Exception:
            pass

    step_responses: list[StepExecutionResponse] = []
    for s in execution.step_executions:
        step_duration_ms: float | None = None
        if s.started_at and s.completed_at:
            step_duration_ms = round((s.completed_at - s.started_at).total_seconds() * 1000, 2)

        s_meta = step_definitions_by_id.get(s.step_id, {})
        step_responses.append(
            StepExecutionResponse(
                id=s.id,
                step_id=s.step_id,
                step_index=s.step_index,
                step_type=s_meta.get("type"),
                connector=s_meta.get("connector"),
                action=s_meta.get("action"),
                status=s.status,
                input_data=s.input_data or {},
                output_data=s.output_data or {},
                error_message=s.error_message,
                started_at=s.started_at,
                completed_at=s.completed_at,
                duration_ms=step_duration_ms,
            )
        )

    exec_duration_ms: float | None = None
    if execution.started_at and execution.completed_at:
        exec_duration_ms = round((execution.completed_at - execution.started_at).total_seconds() * 1000, 2)

    return ExecutionDetail(
        id=execution.id,
        workflow_id=execution.workflow_id,
        workflow_name=execution.workflow.name if execution.workflow else None,
        workflow_version_id=execution.workflow_version_id,
        version_number=execution.version.version_number if execution.version else None,
        organization_id=execution.organization_id,
        status=execution.status,
        trigger_data=execution.trigger_data or {},
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        duration_ms=exec_duration_ms,
        error_message=execution.error_message,
        failure_category=execution.failure_category,
        attempt_number=execution.attempt_number,
        retry_of_execution_id=execution.retry_of_execution_id,
        retry_count=execution.retry_count,
        next_retry_at=execution.next_retry_at,
        last_error_at=execution.last_error_at,
        created_at=execution.created_at,
        steps=step_responses,
    )


def _fail_execution(
    db: Session,
    execution: WorkflowExecution,
    error_message: str,
    category_hint: str | None = None,
) -> WorkflowExecution:
    now = datetime.now(timezone.utc)
    execution.status = "failed"
    execution.error_message = error_message
    execution.completed_at = now
    execution.last_error_at = now

    decision = evaluate_retry(
        error=error_message,
        current_retry_count=execution.retry_count,
        base_time=now,
        category_hint=category_hint,
    )
    execution.failure_category = decision.failure_category.value
    execution.next_retry_at = decision.next_retry_at

    db.commit()
    db.refresh(execution)
    return execution


def execute_workflow(
    db: Session,
    workflow_id: int,
    trigger_data: dict[str, Any],
    user_id: int | None = None,
    organization_id: int | None = None,
    version_id: int | None = None,
    attempt_number: int = 1,
    retry_of_execution_id: int | None = None,
    retry_count: int = 0,
) -> WorkflowExecution:
    """
    Executes a published workflow in a connector-agnostic manner.
    
    Execution Process:
      1. Resolve workflow and verify organization boundaries.
      2. Verify workflow status is 'published' (reject draft or paused).
      3. Resolve the active published WorkflowVersion or specified historical version.
      4. Validate execution safety limits (payload size, step limits).
      5. Load immutable workflow definition.
      6. Create WorkflowExecution record.
      7. Process steps sequentially in order:
         - Conditions: evaluate generically, skip subsequent steps if False.
         - Actions: resolve mappings, fetch adapter via ConnectorRegistry,
           fetch active connection, decrypt credentials in memory, execute action.
      8. Store sanitized step outputs and complete execution.
      9. Mark failed steps and executions appropriately, applying retry policies.
    """
    # 0. Safety limit: check trigger payload size
    try:
        payload_bytes = len(json.dumps(trigger_data).encode("utf-8"))
        if payload_bytes > MAX_PAYLOAD_SIZE:
            raise ValueError(
                f"Trigger payload exceeds maximum allowed size of {MAX_PAYLOAD_SIZE} bytes (got {payload_bytes} bytes)"
            )
    except (TypeError, OverflowError):
        pass

    # 1. Resolve workflow and verify organization boundaries
    if user_id is not None:
        membership = _get_membership(db, user_id, organization_id)
        target_org_id = membership.organization_id
    elif organization_id is not None:
        target_org_id = organization_id
    else:
        target_org_id = None

    wf_query = select(Workflow).where(Workflow.id == workflow_id)
    if target_org_id is not None:
        wf_query = wf_query.where(Workflow.organization_id == target_org_id)

    workflow = db.scalar(wf_query)
    if not workflow:
        raise ValueError("Workflow not found")

    # 2. Confirm workflow is published
    if workflow.status == "draft":
        raise ValueError(
            "Cannot execute workflow with status 'draft'. Only 'published' workflows can be executed."
        )
    if workflow.status == "paused":
        raise ValueError(
            "Cannot execute workflow with status 'paused'. Workflow must be active and published."
        )
    if workflow.status != "published":
        raise ValueError(
            f"Cannot execute workflow with status '{workflow.status}'. Workflow must be 'published' to execute."
        )

    # 3. Resolve the active published version (or specified historical version for retries)
    if version_id is not None:
        version = db.scalar(
            select(WorkflowVersion).where(
                WorkflowVersion.id == version_id,
                WorkflowVersion.workflow_id == workflow.id,
            )
        )
        if not version:
            raise ValueError(f"Workflow version {version_id} not found for workflow {workflow.id}")
    else:
        version = db.scalar(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_id == workflow.id,
                WorkflowVersion.published_at.is_not(None),
            )
            .order_by(WorkflowVersion.version_number.desc())
        )
        if not version:
            raise ValueError("No published version found for this workflow")

    # 4. Load immutable workflow definition and enforce step limit safety
    definition = WorkflowDefinition.model_validate(version.definition)
    if len(definition.steps) > MAX_WORKFLOW_STEPS:
        raise ValueError(
            f"Workflow exceeds maximum allowed steps of {MAX_WORKFLOW_STEPS} (got {len(definition.steps)})"
        )

    # 5. Create WorkflowExecution
    now = datetime.now(timezone.utc)
    sanitized_trigger = _sanitize_payload(dict(trigger_data))
    execution = WorkflowExecution(
        workflow_id=workflow.id,
        workflow_version_id=version.id,
        organization_id=workflow.organization_id,
        status="running",
        trigger_data=sanitized_trigger,
        started_at=now,
        attempt_number=attempt_number,
        retry_of_execution_id=retry_of_execution_id,
        retry_count=retry_count,
    )
    db.add(execution)
    db.flush()

    # 6. Runtime execution context
    context: dict[str, Any] = {
        "trigger": dict(trigger_data),
        "steps": {},
    }
    skip_subsequent = False

    # 7. Process steps in sequential order
    for idx, step in enumerate(definition.steps):
        step_start = datetime.now(timezone.utc)

        if skip_subsequent:
            step_exec = WorkflowStepExecution(
                execution_id=execution.id,
                step_id=step.id,
                step_index=idx,
                status="skipped",
                input_data={},
                output_data={},
                started_at=step_start,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(step_exec)
            continue

        if isinstance(step, ConditionStepDefinition):
            condition_met = evaluate_condition_step(step, context)
            step_end = datetime.now(timezone.utc)
            step_exec = WorkflowStepExecution(
                execution_id=execution.id,
                step_id=step.id,
                step_index=idx,
                status="success",
                input_data={
                    "field": step.field,
                    "operator": step.operator.value if hasattr(step.operator, "value") else str(step.operator),
                    "value": step.value,
                },
                output_data={"condition_met": condition_met},
                started_at=step_start,
                completed_at=step_end,
            )
            db.add(step_exec)
            db.flush()

            context["steps"][step.id] = {"condition_met": condition_met}
            if not condition_met:
                skip_subsequent = True

        elif isinstance(step, ActionStepDefinition):
            step_exec = WorkflowStepExecution(
                execution_id=execution.id,
                step_id=step.id,
                step_index=idx,
                status="running",
                input_data={},
                output_data={},
                started_at=step_start,
            )
            db.add(step_exec)
            db.flush()

            # Resolve mappings
            try:
                resolved_input = resolve_mapping(step.mapping, context)
            except MappingResolutionError as err:
                step_exec.status = "failed"
                step_exec.error_message = f"Mapping resolution error: {str(err)}"
                step_exec.completed_at = datetime.now(timezone.utc)
                return _fail_execution(db, execution, step_exec.error_message, category_hint="mapping_error")

            step_exec.input_data = _sanitize_payload(resolved_input)

            # Resolve connector adapter generically via registry (no connector hardcoding)
            adapter = get_adapter(step.connector)
            if not adapter:
                step_exec.status = "failed"
                step_exec.error_message = f"Connector '{step.connector}' not registered in platform"
                step_exec.completed_at = datetime.now(timezone.utc)
                return _fail_execution(db, execution, step_exec.error_message, category_hint="validation_error")

            # Resolve organization connection
            connection = db.scalar(
                select(Connection).where(
                    Connection.organization_id == workflow.organization_id,
                    Connection.connector_slug == step.connector,
                    Connection.status == "active",
                )
            )
            if not connection:
                step_exec.status = "failed"
                step_exec.error_message = (
                    f"No active connection found for connector '{step.connector}' in this organization"
                )
                step_exec.completed_at = datetime.now(timezone.utc)
                return _fail_execution(db, execution, step_exec.error_message, category_hint="authentication_error")

            # Decrypt credentials in memory only
            credentials = decrypt_credentials(connection.credentials)
            merged_config = {**connection.config, **step.config}

            # Execute action via adapter
            try:
                raw_output = adapter.execute_action(
                    action_slug=step.action,
                    input_data=resolved_input,
                    config=merged_config,
                    credentials=credentials,
                )
                sanitized_output = _sanitize_payload(raw_output)
                step_exec.status = "success"
                step_exec.output_data = sanitized_output
                step_exec.completed_at = datetime.now(timezone.utc)
                db.flush()

                context["steps"][step.id] = sanitized_output
            except ConnectorExecutionError as c_err:
                step_exec.status = "failed"
                step_exec.error_message = _sanitize_payload(c_err.message)
                step_exec.completed_at = datetime.now(timezone.utc)
                return _fail_execution(
                    db,
                    execution,
                    step_exec.error_message,
                    category_hint=c_err.category,
                )
            except Exception as exc:
                step_exec.status = "failed"
                step_exec.error_message = f"Action execution failed: {str(exc)}"
                step_exec.completed_at = datetime.now(timezone.utc)
                return _fail_execution(db, execution, step_exec.error_message)

    # 8. Complete execution
    if execution.status != "failed":
        execution.status = "success"
        execution.failure_category = None
        execution.next_retry_at = None
    execution.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(execution)
    return execution


def get_execution(
    db: Session,
    execution_id: int,
    user_id: int | None = None,
    organization_id: int | None = None,
) -> WorkflowExecution:
    """Retrieves an execution detail record enforcing organization boundaries."""
    if user_id is not None:
        membership = _get_membership(db, user_id, organization_id)
        target_org_id = membership.organization_id
    elif organization_id is not None:
        target_org_id = organization_id
    else:
        target_org_id = None

    query = (
        select(WorkflowExecution)
        .options(
            joinedload(WorkflowExecution.workflow),
            joinedload(WorkflowExecution.version),
            selectinload(WorkflowExecution.step_executions),
        )
        .where(WorkflowExecution.id == execution_id)
    )
    if target_org_id is not None:
        query = query.where(WorkflowExecution.organization_id == target_org_id)

    execution = db.scalar(query)
    if not execution:
        raise ValueError("Execution record not found")
    return execution


def list_executions(
    db: Session,
    workflow_id: int | None = None,
    status_filter: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    user_id: int | None = None,
    organization_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkflowExecution]:
    """Lists workflow execution records filtered by workflow, status, date range, and organization."""
    if user_id is not None:
        try:
            membership = _get_membership(db, user_id, organization_id)
            target_org_id = membership.organization_id
        except ValueError:
            return []
    elif organization_id is not None:
        target_org_id = organization_id
    else:
        target_org_id = None

    query = (
        select(WorkflowExecution)
        .options(
            joinedload(WorkflowExecution.workflow),
            joinedload(WorkflowExecution.version),
            selectinload(WorkflowExecution.step_executions),
        )
        .order_by(WorkflowExecution.created_at.desc())
    )
    if target_org_id is not None:
        query = query.where(WorkflowExecution.organization_id == target_org_id)
    if workflow_id is not None:
        query = query.where(WorkflowExecution.workflow_id == workflow_id)
    if status_filter is not None:
        query = query.where(WorkflowExecution.status == status_filter)
    if start_date is not None:
        query = query.where(WorkflowExecution.created_at >= start_date)
    if end_date is not None:
        query = query.where(WorkflowExecution.created_at <= end_date)

    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)

    return list(db.scalars(query).all())


def retry_workflow_execution(
    db: Session,
    execution_id: int,
    user_id: int | None = None,
    organization_id: int | None = None,
) -> WorkflowExecution:
    """
    Retries a failed workflow execution safely and reproducibly.
    
    Invariants:
      1. Preserves the exact historical workflow version that originally executed.
      2. Preserves the exact trigger context that initiated the original execution.
      3. Validates that original execution exists and its status is 'failed'.
      4. Validates that workflow is not paused or draft.
      5. Increments attempt_number and tracks lineage (retry_of_execution_id, retry_count).
      6. Strict multi-tenant isolation.
    """
    # 1. Resolve and validate the original execution
    original = get_execution(db, execution_id, user_id=user_id, organization_id=organization_id)
    if not original:
        raise ValueError("Execution record not found")

    if original.status != "failed":
        raise ValueError(
            f"Cannot retry execution with status '{original.status}'. Only failed executions can be retried."
        )

    # 2. Verify associated workflow exists and is published
    workflow = original.workflow
    if not workflow:
        workflow = db.scalar(select(Workflow).where(Workflow.id == original.workflow_id))
        if not workflow:
            raise ValueError("Associated workflow not found")

    if workflow.status == "paused":
        raise ValueError("Cannot retry execution for a paused workflow. Resume the workflow first.")
    if workflow.status != "published":
        raise ValueError(
            f"Cannot retry execution for workflow with status '{workflow.status}'. Workflow must be 'published' to execute."
        )

    # 3. Verify original historical version exists
    version = db.scalar(
        select(WorkflowVersion).where(
            WorkflowVersion.id == original.workflow_version_id,
            WorkflowVersion.workflow_id == workflow.id,
        )
    )
    if not version:
        raise ValueError("Original workflow version not found")

    # 4. Attempt tracking and lineage
    new_attempt = (original.attempt_number or 1) + 1
    new_retry_count = (original.retry_count or 0) + 1

    # 5. Execute with exact historical version and original trigger data
    return execute_workflow(
        db=db,
        workflow_id=workflow.id,
        trigger_data=original.trigger_data or {},
        organization_id=workflow.organization_id,
        version_id=original.workflow_version_id,
        attempt_number=new_attempt,
        retry_of_execution_id=original.id,
        retry_count=new_retry_count,
    )


def get_workflow_health(
    db: Session,
    workflow_id: int,
    user_id: int | None = None,
    organization_id: int | None = None,
) -> dict[str, Any]:
    """
    Computes derived health and reliability status for a workflow based on recent execution history.
    Status values: 'healthy', 'needs_attention', 'retrying', 'paused', 'never_run'.
    """
    if user_id is not None:
        membership = _get_membership(db, user_id, organization_id)
        target_org_id = membership.organization_id
    elif organization_id is not None:
        target_org_id = organization_id
    else:
        target_org_id = None

    wf_query = select(Workflow).where(Workflow.id == workflow_id)
    if target_org_id is not None:
        wf_query = wf_query.where(Workflow.organization_id == target_org_id)
    workflow = db.scalar(wf_query)
    if not workflow:
        raise ValueError("Workflow not found")

    now = datetime.now(timezone.utc)

    # Query recent executions (up to 50)
    recent_execs = list(
        db.scalars(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow.id)
            .order_by(WorkflowExecution.created_at.desc())
            .limit(50)
        ).all()
    )

    total_count = len(recent_execs)
    if total_count == 0:
        return {
            "workflow_id": workflow.id,
            "status": "paused" if workflow.status == "paused" else "never_run",
            "success_rate_percent": 100.0,
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "consecutive_failures": 0,
            "is_retrying": False,
            "next_retry_at": None,
            "last_executed_at": None,
            "last_error_at": None,
            "last_error_message": None,
        }

    successful_count = sum(1 for e in recent_execs if e.status == "success")
    failed_count = sum(1 for e in recent_execs if e.status == "failed")
    success_rate = round((successful_count / total_count) * 100, 2)

    # Compute consecutive failures starting from most recent
    consecutive_failures = 0
    for e in recent_execs:
        if e.status == "failed":
            consecutive_failures += 1
        elif e.status == "success":
            break

    # Determine if any execution has a pending retry in the future or is running
    def _is_future_retry(e: WorkflowExecution) -> bool:
        if e.status != "failed" or e.next_retry_at is None:
            return False
        dt = e.next_retry_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt > now

    is_retrying = any(e.status == "running" or _is_future_retry(e) for e in recent_execs)

    future_retry_times = [
        (e.next_retry_at.replace(tzinfo=timezone.utc) if e.next_retry_at.tzinfo is None else e.next_retry_at)
        for e in recent_execs
        if _is_future_retry(e)
    ]
    next_retry_at = min(future_retry_times) if future_retry_times else None

    last_exec = recent_execs[0]
    last_failed = next((e for e in recent_execs if e.status == "failed"), None)

    # Derive workflow status
    if workflow.status == "paused":
        derived_status = "paused"
    elif is_retrying:
        derived_status = "retrying"
    elif consecutive_failures >= 2 or (total_count >= 3 and success_rate < 50.0):
        derived_status = "needs_attention"
    else:
        derived_status = "healthy"

    return {
        "workflow_id": workflow.id,
        "status": derived_status,
        "success_rate_percent": success_rate,
        "total_executions": total_count,
        "successful_executions": successful_count,
        "failed_executions": failed_count,
        "consecutive_failures": consecutive_failures,
        "is_retrying": is_retrying,
        "next_retry_at": next_retry_at,
        "last_executed_at": last_exec.created_at,
        "last_error_at": last_failed.last_error_at if last_failed else None,
        "last_error_message": last_failed.error_message if last_failed else None,
    }
