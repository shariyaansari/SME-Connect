from sqlalchemy.orm import Session
from sqlalchemy import select
import secrets

from app.database.models import Invitation, Membership, Organization
from app.database.models import (
    Membership,
    Organization,
    User,
)
from app.modules.organizations.schemas import (
    OrganizationMemberResponse,
    PendingInvitationResponse,
)

def create_organization(
    db: Session,
    user_id: int,
    name: str,
) -> Organization:
    organization = Organization(
        name=name,
    )

    db.add(organization)
    db.flush()

    membership = Membership(
        user_id=user_id,
        organization_id= organization.id,
        role="Admin",
    )

    db.add(membership)
    db.commit()
    db.refresh(organization)

    return organization

def get_user_organization(
    db: Session,
    user_id: int,
) -> tuple[Organization, str] | None:
    result = db.execute(
        select(Organization, Membership.role)
        .join(
            Membership,
            Membership.organization_id == Organization.id,
        )
        .where(Membership.user_id == user_id)
    ).first()

    if not result:
        return None

    organization, role = result

    return organization, role

def get_organization_members(
    db: Session,
    user_id: int,
) -> list[OrganizationMemberResponse]:
    organization_result = db.execute(
        select(Membership.organization_id)
        .where(Membership.user_id == user_id)
    ).first()

    if not organization_result:
        return []

    organization_id = organization_result[0]

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
            Membership.organization_id == organization_id
        )
    ).all()

    return [
        OrganizationMemberResponse(
            id=member.id,
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
) -> Invitation:
    organization_result = db.execute(
        select(Membership.organization_id)
        .where(Membership.user_id == user_id)
    ).first()

    if not organization_result:
        raise ValueError("Organization not found")

    organization_id = organization_result[0]

    membership = db.execute(
        select(Membership)
        .where(
            Membership.user_id == user_id,
            Membership.organization_id == organization_id,
        )
    ).scalar_one()

    if membership.role != "Admin":
        raise PermissionError(
            "Only Admins can invite members"
        )

    existing_membership = db.execute(
        select(Membership)
        .join(User, Membership.user_id == User.id)
        .where(
            Membership.organization_id == organization_id,
            User.email == email,
        )
    ).first()

    if existing_membership:
        raise ValueError(
            "User is already a member"
        )

    token = secrets.token_urlsafe(32)

    invitation = Invitation(
        organization_id=organization_id,
        email=email,
        role=role,
        token=token,
    )

    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return invitation

def get_pending_invitations(
    db: Session,
    email: str,
) -> list[PendingInvitationResponse]:
    invitations = db.scalars(
        select(Invitation)
        .where(
            Invitation.email == email,
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

    if user.email.lower() != invitation.email.lower():
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
        raise ValueError(
            "User is already a member"
        )

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
) -> Membership:
    allowed_roles = {"Admin", "Editor", "Viewer"}

    if role not in allowed_roles:
        raise ValueError(
            "Role must be Admin, Editor, or Viewer"
        )

    current_membership = db.execute(
        select(Membership)
        .where(
            Membership.user_id == current_user_id,
        )
    ).scalar_one_or_none()

    if not current_membership:
        raise ValueError("Current user is not a member")

    if current_membership.role != "Admin":
        raise PermissionError(
            "Only Admins can change member roles"
        )

    target_membership = db.get(
        Membership,
        member_id,
    )

    if not target_membership:
        raise ValueError("Membership not found")

    if (
        target_membership.organization_id
        != current_membership.organization_id
    ):
        raise PermissionError(
            "Member belongs to another organization"
        )

    target_membership.role = role

    db.commit()
    db.refresh(target_membership)

    return target_membership