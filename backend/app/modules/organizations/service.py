import secrets
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Invitation, Membership, Organization, User
from app.modules.organizations.schemas import (
    OrganizationMemberResponse,
    PendingInvitationResponse,
    UserOrganizationItem,
)

ALLOWED_ROLES = {"Admin", "Editor", "Viewer"}


def create_organization(
    db: Session,
    user_id: int,
    name: str,
) -> Organization:
    organization = Organization(
        name=name.strip(),
    )

    db.add(organization)
    db.flush()

    membership = Membership(
        user_id=user_id,
        organization_id=organization.id,
        role="Admin",
    )

    db.add(membership)
    db.commit()
    db.refresh(organization)

    return organization


def get_user_organizations(
    db: Session,
    user_id: int,
) -> list[UserOrganizationItem]:
    results = db.execute(
        select(Organization.id, Organization.name, Membership.role)
        .join(
            Membership,
            Membership.organization_id == Organization.id,
        )
        .where(Membership.user_id == user_id)
        .order_by(Organization.id)
    ).all()

    return [
        UserOrganizationItem(
            id=row.id,
            name=row.name,
            role=row.role,
        )
        for row in results
    ]


def get_user_organization(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> tuple[Organization, str] | None:
    query = (
        select(Organization, Membership.role)
        .join(
            Membership,
            Membership.organization_id == Organization.id,
        )
        .where(Membership.user_id == user_id)
    )

    if organization_id is not None:
        query = query.where(Organization.id == organization_id)

    result = db.execute(query.order_by(Organization.id)).first()

    if not result:
        return None

    organization, role = result
    return organization, role


def get_organization_members(
    db: Session,
    user_id: int,
    organization_id: int | None = None,
) -> list[OrganizationMemberResponse]:
    if organization_id is None:
        org_result = db.execute(
            select(Membership.organization_id)
            .where(Membership.user_id == user_id)
            .order_by(Membership.id)
        ).first()

        if not org_result:
            return []
        target_org_id = org_result[0]
    else:
        # Verify user is a member of the requested organization
        caller_membership = db.execute(
            select(Membership.id).where(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
        ).first()
        if not caller_membership:
            return []
        target_org_id = organization_id

    members = db.execute(
        select(
            User.id,
            User.name,
            User.email,
            Membership.role,
        )
        .join(
            Membership,
            Membership.user_id == User.id,
        )
        .where(
            Membership.organization_id == target_org_id
        )
        .order_by(User.id)
    ).all()

    return [
        OrganizationMemberResponse(
            id=member.id,
            user_id=member.id,
            name=member.name,
            email=member.email,
            role=member.role,
        )
        for member in members
    ]


def create_invitation(
    db: Session,
    user_id: int,
    email: str,
    role: str,
    organization_id: int | None = None,
) -> Invitation:
    if role not in ALLOWED_ROLES:
        raise ValueError("Role must be Admin, Editor, or Viewer")

    normalized_email = email.lower().strip()

    if organization_id is None:
        org_result = db.execute(
            select(Membership.organization_id)
            .where(Membership.user_id == user_id)
            .order_by(Membership.id)
        ).first()

        if not org_result:
            raise ValueError("Organization not found")

        target_org_id = org_result[0]
    else:
        target_org_id = organization_id

    # Check caller has Admin role in that organization
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.organization_id == target_org_id,
        )
    )

    if not membership:
        raise ValueError("Organization not found")

    if membership.role != "Admin":
        raise PermissionError("Only Admins can invite members")

    # Check if user is already a member
    existing_membership = db.execute(
        select(Membership)
        .join(User, Membership.user_id == User.id)
        .where(
            Membership.organization_id == target_org_id,
            func.lower(User.email) == normalized_email,
        )
    ).first()

    if existing_membership:
        raise ValueError("User is already a member")

    # Check if invitation already pending
    existing_invite = db.scalar(
        select(Invitation).where(
            Invitation.organization_id == target_org_id,
            func.lower(Invitation.email) == normalized_email,
            Invitation.status == "pending",
        )
    )

    if existing_invite:
        raise ValueError("An invitation is already pending for this email")

    token = secrets.token_urlsafe(32)

    invitation = Invitation(
        organization_id=target_org_id,
        email=normalized_email,
        role=role,
        token=token,
        status="pending",
    )

    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return invitation


def get_pending_invitations(
    db: Session,
    email: str,
) -> list[PendingInvitationResponse]:
    normalized_email = email.lower().strip()

    invitations = db.scalars(
        select(Invitation)
        .where(
            func.lower(Invitation.email) == normalized_email,
            Invitation.status == "pending",
        )
        .order_by(Invitation.id)
    ).all()

    return [
        PendingInvitationResponse(
            id=invitation.id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
        )
        for invitation in invitations
    ]


def accept_invitation(
    db: Session,
    user_id: int,
    token: str,
) -> tuple[int, str]:
    invitation = db.scalar(
        select(Invitation).where(Invitation.token == token)
    )

    if not invitation:
        raise ValueError("Invitation not found")

    if invitation.status != "pending":
        raise ValueError("Invitation is no longer pending")

    user = db.get(User, user_id)
    if not user:
        raise ValueError("User not found")

    if user.email.lower().strip() != invitation.email.lower().strip():
        raise PermissionError(
            "This invitation was sent to another email address"
        )

    existing_membership = db.execute(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.organization_id == invitation.organization_id,
        )
    ).scalar_one_or_none()

    if existing_membership:
        raise ValueError("User is already a member")

    membership = Membership(
        user_id=user_id,
        organization_id=invitation.organization_id,
        role=invitation.role,
    )

    invitation.status = "accepted"

    db.add(membership)
    db.commit()

    return invitation.organization_id, invitation.role


def update_member_role(
    db: Session,
    current_user_id: int,
    member_id: int,
    role: str,
    organization_id: int | None = None,
) -> Membership:
    if role not in ALLOWED_ROLES:
        raise ValueError("Role must be Admin, Editor, or Viewer")

    # Find organizations where caller is Admin
    admin_org_query = select(Membership.organization_id).where(
        Membership.user_id == current_user_id,
        Membership.role == "Admin",
    )
    if organization_id is not None:
        admin_org_query = admin_org_query.where(
            Membership.organization_id == organization_id
        )

    admin_org_ids = db.scalars(admin_org_query).all()

    if not admin_org_ids:
        raise PermissionError("Only Admins can change member roles")

    # Locate target membership by either user_id or membership id within admin orgs
    target_membership = db.scalar(
        select(Membership).where(
            Membership.organization_id.in_(admin_org_ids),
            (Membership.user_id == member_id) | (Membership.id == member_id),
        )
    )

    if not target_membership:
        raise ValueError("Member not found in your organization")

    # Guard against demoting the sole Admin
    if target_membership.role == "Admin" and role != "Admin":
        admin_count = db.scalar(
            select(func.count(Membership.id)).where(
                Membership.organization_id == target_membership.organization_id,
                Membership.role == "Admin",
            )
        )
        if admin_count is not None and admin_count <= 1:
            raise ValueError("Cannot demote the sole Admin of the organization")

    target_membership.role = role
    db.commit()
    db.refresh(target_membership)

    return target_membership