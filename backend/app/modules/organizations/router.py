from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.connection import get_db
from app.database.models import User
from app.modules.organizations.schemas import (
    CurrentOrganizationResponse,
    InvitationAcceptRequest,
    InvitationAcceptResponse,
    InvitationCreateRequest,
    InvitationResponse,
    MemberRoleUpdateRequest,
    MemberRoleUpdateResponse,
    OrganizationCreateRequest,
    OrganizationMemberResponse,
    OrganizationResponse,
    PendingInvitationResponse,
    UserOrganizationItem,
)
from app.modules.organizations.service import (
    accept_invitation,
    create_invitation,
    create_organization,
    get_organization_members,
    get_pending_invitations,
    get_user_organization,
    get_user_organizations,
    update_member_role,
)

router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"],
)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_endpoint(
    data: OrganizationCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return create_organization(
        db=db,
        user_id=current_user.id,
        name=data.name,
    )


@router.get(
    "",
    response_model=list[UserOrganizationItem],
)
def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_user_organizations(
        db=db,
        user_id=current_user.id,
    )


@router.get(
    "/me",
    response_model=CurrentOrganizationResponse,
)
def get_current_organization(
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = get_user_organization(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    organization, role = result

    return CurrentOrganizationResponse(
        id=organization.id,
        name=organization.name,
        role=role,
    )


@router.get(
    "/members",
    response_model=list[OrganizationMemberResponse],
)
def get_members(
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_organization_members(
        db=db,
        user_id=current_user.id,
        organization_id=organization_id,
    )


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    data: InvitationCreateRequest,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        invitation = create_invitation(
            db=db,
            user_id=current_user.id,
            email=data.email,
            role=data.role,
            organization_id=organization_id,
        )
        return InvitationResponse(
            id=invitation.id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=invitation.role,
            status=invitation.status,
            token=invitation.token,
        )

    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )


@router.get(
    "/invitations/pending",
    response_model=list[PendingInvitationResponse],
)
def get_pending_invitations_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return get_pending_invitations(
        db=db,
        email=current_user.email,
    )


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptResponse,
)
def accept_invitation_endpoint(
    data: InvitationAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        organization_id, role = accept_invitation(
            db=db,
            user_id=current_user.id,
            token=data.token,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    return InvitationAcceptResponse(
        message="Invitation accepted",
        organization_id=organization_id,
        role=role,
    )


@router.patch(
    "/members/{member_id}",
    response_model=MemberRoleUpdateResponse,
)
def update_member_role_endpoint(
    member_id: int,
    data: MemberRoleUpdateRequest,
    organization_id: int | None = Query(None, description="Optional organization ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        membership = update_member_role(
            db=db,
            current_user_id=current_user.id,
            member_id=member_id,
            role=data.role,
            organization_id=organization_id,
        )
    except PermissionError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(error),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    return MemberRoleUpdateResponse(
        message="Member role updated successfully",
        member_id=member_id,
        role=membership.role,
    )