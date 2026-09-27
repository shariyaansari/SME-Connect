# Module 1 — User & Organization Management

## 1. Purpose

Manage user accounts, authentication, organizations/workspaces, memberships,
roles, and basic organization access.

---

## 2. MVP Scope

- User registration
- User login
- Email verification
- Organization/workspace creation
- View current organization
- Organization member listing
- Member invitation
- Member role management
- Role-based access control

### Roles

| Role | Access |
|---|---|
| Admin | Full organization management |
| Editor | Create and manage workflows |
| Viewer | View workflows and execution results |

---

## 3. Domain Model

```text
                    ┌──────────────┐
                    │     User     │
                    └──────┬───────┘
                           │
                           │ 1:N
                           ▼
                    ┌──────────────┐
                    │ Membership   │
                    └──────┬───────┘
                           │
                           │ N:1
                           ▼
                  ┌──────────────────┐
                  │  Organization    │
                  └──────┬───────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
       Connections              Workflows
```

A user belongs to an organization through Membership.

## 4. Database Entities

| Field          | Purpose               |
| -------------- | --------------------- |
| id             | Unique user ID        |
| name           | User's name           |
| email          | Login email           |
| password_hash  | Hashed password       |
| email_verified | Verification status   |
| created_at     | Creation timestamp    |
| updated_at     | Last update timestamp |

#### Organizations 

| Field      | Purpose                     |
| ---------- | --------------------------- |
| id         | Unique organization ID      |
| name       | Organization/workspace name |
| created_at | Creation timestamp          |
| updated_at | Last update timestamp       |


#### memberships 

| Field           | Purpose                  |
| --------------- | ------------------------ |
| id              | Unique membership ID     |
| user_id         | References user          |
| organization_id | References organization  |
| role            | Admin / Editor / Viewer  |
| created_at      | Membership creation time |

#### Invitations

| Field           | Purpose                               |
| --------------- | ------------------------------------- |
| id              | Unique invitation ID                  |
| organization_id | References organization               |
| email           | Invitee email address                 |
| role            | Admin / Editor / Viewer               |
| token           | Unique secure invitation token        |
| status          | Invitation status (pending, accepted) |
| created_at      | Invitation creation timestamp         |

#### Audit Logs (`audit_logs`)

| Field           | Purpose                                              |
| --------------- | ---------------------------------------------------- |
| id              | Unique audit log ID                                  |
| organization_id | References organization (multi-tenant scope)         |
| user_id         | References user who initiated action                 |
| action          | Event action type (e.g. `ORGANIZATION_CREATED`)      |
| resource_type   | Resource entity (e.g. `Organization`, `Membership`)  |
| resource_id     | Primary key ID of affected resource                  |
| details         | Human-readable event description (no secrets/tokens) |
| created_at      | Timestamp when event occurred                        |

## 5. API Design  

| Method | Endpoint             | Purpose                   |
| ------ | -------------------- | ------------------------- |
| POST   | `/auth/register`     | Create user               |
| POST   | `/auth/login`        | Authenticate user         |
| POST   | `/auth/refresh`      | Refresh JWT access token  |
| GET    | `/auth/me`           | Current user profile      |
| POST   | `/auth/verify-email` | Verify email              |

#### Organization

| Method | Endpoint                             | Purpose                   |
| ------ | ------------------------------------ | ------------------------- |
| POST   | `/organizations`                     | Create organization       |
| GET    | `/organizations`                     | List user's organizations |
| GET    | `/organizations/me`                  | Get current organization  |
| GET    | `/organizations/members`             | List members              |
| POST   | `/organizations/invitations`         | Invite member             |
| GET    | `/organizations/invitations/pending` | View pending invitations  |
| POST   | `/organizations/invitations/accept`  | Accept invitation         |
| PATCH  | `/organizations/members/{id}`        | Change member role        |
| GET    | `/organizations/audit-logs`          | View organization audit trail |

## Flow 

1. Registration Flow

```
User
 │
 │ POST /auth/register
 ▼
FastAPI
 │
 ├── Validate input
 ├── Check email uniqueness
 ├── Hash password
 └── Create user
 │
 ▼
PostgreSQL
 │
 ▼
Registration response
```

2. Authentication Flow
```
User
 │
 │ email + password
 ▼
POST /auth/login
 │
 ▼
Validate credentials
 │
 ▼
Generate access/refresh tokens
 │
 ▼
Authenticated API requests
```

3. Organization Flow

```
User
 │
 │ Create organization
 ▼
Organization
 │
 └── Membership
       │
       └── User = Admin
```

4. Access Control
```
Request
   │
   ▼
Authentication
   │
   ▼
Identify User
   │
   ▼
Find Organization Membership
   │
   ▼
Check Role
   │
   ├── Allowed ──► Continue
   │
   └── Denied ───► 403 Forbidden
```

5. Invitation Flow

```text
Admin
  ↓
Invite email
  ↓
Invitation (pending)
  ↓
User may register
  ↓
User logs in
  ↓
View pending invitation
  ↓
Accept
  ↓
Membership created
  ↓
Invitation (accepted)
```

An invitation can be created for an email address that does not yet have an account. Registration does not automatically create organization membership; membership is created when the user accepts the invitation.

#### Lifecycle Details

1. **Admin sends invite (`POST /organizations/invitations`)**: Only users with the `Admin` role in an organization can invite new members. Invitations specify the invitee's email and role (`Admin`, `Editor`, or `Viewer`).
2. **Pending status & secure token**: An invitation record is created in the database with status `pending` and a cryptographically secure random token.
3. **Registration (`POST /auth/register`)**: If the invitee does not already have an account, they can register at any time. Registration does not automatically grant organization membership or auto-accept invitations.
4. **Login (`POST /auth/login`)**: The invitee logs in to obtain an authenticated session / JWT access token.
5. **View pending invitations (`GET /organizations/invitations/pending`)**: Authenticated users can query for invitations matching their email address that are currently in `pending` status.
6. **Accept invitation (`POST /organizations/invitations/accept`)**: The invited user submits the invitation token. The system verifies that the authenticated user's email strictly matches the invitation email.
7. **Membership created & status updated**: A new `Membership` record is created linking the user to the organization with the assigned role, and the invitation status transitions to `accepted`.

### 6. Audit Trail Events

To ensure transparency and compliance across multi-tenant workspaces, the system records immutable audit log entries committed synchronously with critical state transitions:

| Event Action | Triggering Operation | Resource Type | Recorded Details |
|---|---|---|---|
| `ORGANIZATION_CREATED` | Workspace creation | `Organization` | "Organization created" |
| `MEMBER_INVITED` | Admin sends team invitation | `Invitation` | "Invitation created for {email}" (tokens never logged) |
| `INVITATION_ACCEPTED` | Recipient accepts invitation | `Membership` | "Invitation accepted with role {role}" |
| `MEMBER_ROLE_UPDATED` | Admin modifies member's role | `Membership` | "Role changed from {old_role} to {new_role}" |
