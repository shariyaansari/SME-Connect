from pydantic import BaseModel, EmailStr, Field


class OrganizationCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)


class OrganizationResponse(BaseModel):
    id: int
    name: str
    
class CurrentOrganizationResponse(BaseModel):
    id: int
    name: str
    role: str
    
class OrganizationMemberResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    
class InvitationCreateRequest(BaseModel):
    email: EmailStr
    role: str = "Viewer"


class InvitationResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    status: str
    token: str


class PendingInvitationResponse(BaseModel):
    id: int
    organization_id: int
    email: EmailStr
    role: str
    status: str


class InvitationAcceptRequest(BaseModel):
    token: str

class InvitationAcceptResponse(BaseModel):
    message: str
    organization_id: int
    role: str
    
class MemberRoleUpdateRequest(BaseModel):
    role: str