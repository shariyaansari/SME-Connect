from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Notification, Workflow, WorkflowExecution
from app.modules.executions.resolver import sanitize_error_message
from app.modules.executions.retry_policy import explain_failure_for_user


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_notification(
    db: Session,
    organization_id: int,
    title: str,
    message: str,
    severity: str = "warning",
    notification_type: str = "general",
    workflow_id: int | None = None,
    execution_id: int | None = None,
) -> Notification:
    notif = Notification(
        organization_id=organization_id,
        workflow_id=workflow_id,
        execution_id=execution_id,
        title=title,
        message=message,
        severity=severity,
        notification_type=notification_type,
        is_read=False,
        created_at=_utc_now(),
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif


def check_and_notify_repeated_failure(
    db: Session,
    workflow_id: int,
    execution_id: int,
    organization_id: int,
    threshold: int = 2,
) -> Notification | None:
    """
    Evaluates recent execution history for a workflow.
    If consecutive failures reach or exceed the threshold (default: 2),
    generates an in-app notification with plain-language diagnostics.
    Avoids notification spam by updating existing unread alerts for the same workflow.
    """
    workflow = db.scalar(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == organization_id,
        )
    )
    if not workflow:
        return None

    # Query last 10 executions for this workflow
    recent_execs = list(
        db.scalars(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.organization_id == organization_id,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(10)
        ).all()
    )

    if not recent_execs:
        return None

    # Count consecutive failures starting from the most recent
    consecutive_failures = 0
    for e in recent_execs:
        if e.status == "failed":
            consecutive_failures += 1
        elif e.status == "success":
            break

    if consecutive_failures < threshold:
        return None

    latest_exec = recent_execs[0]
    diag = explain_failure_for_user(latest_exec.failure_category, latest_exec.error_message)
    sanitized_err = sanitize_error_message(latest_exec.error_message)

    title = f"Workflow '{workflow.name}' Failed Repeatedly ({consecutive_failures}x)"
    body_lines = [
        f"This workflow has encountered {consecutive_failures} consecutive failures.",
        f"Diagnosed Issue: {diag.get('title', 'Execution Error')}",
        f"Explanation: {diag.get('explanation', sanitized_err)}",
    ]
    if diag.get("action"):
        body_lines.append(f"Recommended Action: {diag['action']}")

    message = "\n".join(body_lines)
    severity = "critical" if consecutive_failures >= 3 else "warning"

    # Check if an unread notification already exists for this workflow
    existing = db.scalar(
        select(Notification).where(
            Notification.organization_id == organization_id,
            Notification.workflow_id == workflow_id,
            Notification.notification_type == "repeated_failure",
            Notification.is_read.is_(False),
        )
    )

    if existing:
        existing.title = title
        existing.message = message
        existing.severity = severity
        existing.execution_id = execution_id
        existing.created_at = _utc_now()
        db.commit()
        db.refresh(existing)
        return existing

    return create_notification(
        db=db,
        organization_id=organization_id,
        title=title,
        message=message,
        severity=severity,
        notification_type="repeated_failure",
        workflow_id=workflow_id,
        execution_id=execution_id,
    )


def list_notifications(
    db: Session,
    organization_id: int,
    is_read: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int, int]:
    """
    Returns paginated notifications for the organization, enriched with workflow names.
    Also returns total count and unread count.
    """
    base_query = select(Notification).where(Notification.organization_id == organization_id)
    if is_read is not None:
        base_query = base_query.where(Notification.is_read == is_read)

    total = db.scalar(
        select(func.count(Notification.id)).where(Notification.organization_id == organization_id)
    ) or 0

    unread_count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.organization_id == organization_id,
            Notification.is_read.is_(False),
        )
    ) or 0

    notifs = list(
        db.scalars(
            base_query.order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    # Collect workflow names efficiently
    wf_ids = {n.workflow_id for n in notifs if n.workflow_id is not None}
    wf_names: dict[int, str] = {}
    if wf_ids:
        rows = db.execute(
            select(Workflow.id, Workflow.name).where(Workflow.id.in_(wf_ids))
        ).all()
        wf_names = {row[0]: row[1] for row in rows}

    items = []
    for n in notifs:
        items.append({
            "id": n.id,
            "organization_id": n.organization_id,
            "workflow_id": n.workflow_id,
            "workflow_name": wf_names.get(n.workflow_id) if n.workflow_id else None,
            "execution_id": n.execution_id,
            "title": n.title,
            "message": n.message,
            "severity": n.severity,
            "notification_type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at,
            "read_at": n.read_at,
        })

    return items, total, unread_count


def get_unread_count(db: Session, organization_id: int) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.organization_id == organization_id,
            Notification.is_read.is_(False),
        )
    ) or 0


def mark_notification_as_read(
    db: Session,
    notification_id: int,
    organization_id: int,
) -> Notification:
    notif = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == organization_id,
        )
    )
    if not notif:
        raise ValueError("Notification not found")

    notif.is_read = True
    notif.read_at = _utc_now()
    db.commit()
    db.refresh(notif)
    return notif


def mark_all_notifications_as_read(
    db: Session,
    organization_id: int,
) -> int:
    now = _utc_now()
    unread_notifs = list(
        db.scalars(
            select(Notification).where(
                Notification.organization_id == organization_id,
                Notification.is_read.is_(False),
            )
        ).all()
    )
    for n in unread_notifs:
        n.is_read = True
        n.read_at = now
    db.commit()
    return len(unread_notifs)


def delete_notification(
    db: Session,
    notification_id: int,
    organization_id: int,
) -> None:
    notif = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.organization_id == organization_id,
        )
    )
    if not notif:
        raise ValueError("Notification not found")

    db.delete(notif)
    db.commit()
