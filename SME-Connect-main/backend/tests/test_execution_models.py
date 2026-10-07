import pytest
from datetime import datetime, timezone
from sqlalchemy import select
from app.database.models import (
    Organization,
    User,
    Workflow,
    WorkflowExecution,
    WorkflowStepExecution,
    WorkflowVersion,
)


def test_workflow_execution_creation_and_defaults(db_session):
    now = datetime.now(timezone.utc)
    user = User(
        name="Automation User",
        email="auto@sme.com",
        password_hash="hashed_pw",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name="Operations Org")
    db_session.add(org)
    db_session.flush()

    wf = Workflow(
        organization_id=org.id,
        name="Order Sync Workflow",
        status="published",
        created_by=user.id,
    )
    db_session.add(wf)
    db_session.flush()

    version = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition={
            "trigger": {"connector": "google_sheets", "event": "new_row", "config": {}},
            "steps": [],
        },
        created_by=user.id,
        published_at=now,
    )
    db_session.add(version)
    db_session.flush()

    execution = WorkflowExecution(
        workflow_id=wf.id,
        workflow_version_id=version.id,
        organization_id=org.id,
        trigger_data={"row_index": 2, "values": {"Name": "Acme Corp"}},
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    assert execution.id is not None
    assert execution.status == "pending"
    assert execution.trigger_data == {"row_index": 2, "values": {"Name": "Acme Corp"}}
    assert execution.started_at is None
    assert execution.completed_at is None
    assert execution.error_message is None
    assert execution.created_at is not None
    assert execution.workflow.id == wf.id
    assert execution.version.id == version.id
    assert execution.organization.id == org.id
    assert execution.step_executions == []


def test_step_execution_ordering_and_cascade(db_session):
    now = datetime.now(timezone.utc)
    user = User(
        name="Step Test User",
        email="steptest@sme.com",
        password_hash="hashed_pw",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name="Step Test Org")
    db_session.add(org)
    db_session.flush()

    wf = Workflow(
        organization_id=org.id,
        name="Multi Step Workflow",
        status="published",
        created_by=user.id,
    )
    db_session.add(wf)
    db_session.flush()

    version = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition={"trigger": {"connector": "google_sheets", "event": "new_row"}, "steps": []},
        created_by=user.id,
        published_at=now,
    )
    db_session.add(version)
    db_session.flush()

    execution = WorkflowExecution(
        workflow_id=wf.id,
        workflow_version_id=version.id,
        organization_id=org.id,
        status="running",
        trigger_data={"order_id": "1001"},
        started_at=now,
    )
    db_session.add(execution)
    db_session.flush()

    step2 = WorkflowStepExecution(
        execution_id=execution.id,
        step_id="step-send-whatsapp",
        step_index=1,
        status="pending",
        input_data={"phone": "9998887776"},
    )
    step1 = WorkflowStepExecution(
        execution_id=execution.id,
        step_id="step-create-crm-lead",
        step_index=0,
        status="success",
        input_data={"name": "Alice"},
        output_data={"lead_id": "lead_123"},
        started_at=now,
        completed_at=now,
    )
    db_session.add_all([step2, step1])
    db_session.commit()
    db_session.refresh(execution)

    # Verify ordering by step_index
    assert len(execution.step_executions) == 2
    assert execution.step_executions[0].step_id == "step-create-crm-lead"
    assert execution.step_executions[0].step_index == 0
    assert execution.step_executions[0].status == "success"
    assert execution.step_executions[1].step_id == "step-send-whatsapp"
    assert execution.step_executions[1].step_index == 1

    # Test cascade deletion of step executions when parent execution is deleted
    db_session.delete(execution)
    db_session.commit()

    remaining_steps = db_session.scalars(
        select(WorkflowStepExecution).where(WorkflowStepExecution.execution_id == execution.id)
    ).all()
    assert len(remaining_steps) == 0


def test_workflow_and_organization_cascade_deletion(db_session):
    now = datetime.now(timezone.utc)
    user = User(
        name="Cascade User",
        email="cascade@sme.com",
        password_hash="hashed_pw",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organization(name="Cascade Org")
    db_session.add(org)
    db_session.flush()

    wf = Workflow(
        organization_id=org.id,
        name="Cascade Workflow",
        status="published",
        created_by=user.id,
    )
    db_session.add(wf)
    db_session.flush()

    version = WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        definition={"trigger": {"connector": "google_sheets", "event": "new_row"}, "steps": []},
        created_by=user.id,
        published_at=now,
    )
    db_session.add(version)
    db_session.flush()

    execution = WorkflowExecution(
        workflow_id=wf.id,
        workflow_version_id=version.id,
        organization_id=org.id,
        trigger_data={"event": "ping"},
    )
    db_session.add(execution)
    db_session.commit()

    exec_id = execution.id

    # Deleting workflow should cascade to executions
    db_session.delete(wf)
    db_session.commit()

    found = db_session.scalar(select(WorkflowExecution).where(WorkflowExecution.id == exec_id))
    assert found is None
