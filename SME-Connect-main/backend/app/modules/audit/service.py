from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import AuditLog, Membership


def create_audit_log(
    db: Session,
    organization_id: int,
    user_id: int | None = None,
    action: str = "",
    resource_type: str = "",
    resource_id: int | None = None,
    details: str | None = None,
) -> AuditLog:
    log = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    )

    db.add(log)
    db.flush()

    return log


def list_organization_audit_logs(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> list[AuditLog]:
    if organization_id is None:
        membership = db.execute(
            select(Membership.organization_id)
            .where(Membership.user_id == user_id)
            .order_by(Membership.id)
        ).first()

        if not membership:
            return []
        target_org_id = membership[0]
    else:
        membership = db.execute(
            select(Membership.id).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
        ).first()

        if not membership:
            raise PermissionError("User does not belong to the specified organization")
        target_org_id = organization_id

    logs = db.scalars(
        select(AuditLog)
        .where(AuditLog.organization_id == target_org_id)
        .order_by(AuditLog.id.asc())
    ).all()

    return list(logs)
