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


## 5. API Design  

| Method | Endpoint             | Purpose           |
| ------ | -------------------- | ----------------- |
| POST   | `/auth/register`     | Create user       |
| POST   | `/auth/login`        | Authenticate user |
| POST   | `/auth/verify-email` | Verify email      |

#### Organization

| Method | Endpoint                      | Purpose                  |
| ------ | ----------------------------- | ------------------------ |
| POST   | `/organizations`              | Create organization      |
| GET    | `/organizations/me`           | Get current organization |
| GET    | `/organizations/members`      | List members             |
| POST   | `/organizations/invitations`  | Invite member            |
| PATCH  | `/organizations/members/{id}` | Change member role       |

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