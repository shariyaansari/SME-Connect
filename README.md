# SME Connect

SME Connect is an automation platform for small and medium-sized businesses. It brings organization management and third-party business connections into one workspace, with connector-agnostic workflows planned as the next major module.

## Current Status

The repository currently contains a working foundation for:

- User registration, login, email verification, token refresh, and authenticated user details
- Organization creation, membership, invitations, roles, and audit logs
- Connector catalog, connection management, connection testing, and connector adapters
- React/Vite frontend screens for authentication, team workspaces, connected apps, and workflow planning

Workflow management is specified in [`docs/module-3-workflows.md`](docs/module-3-workflows.md) and is planned for implementation. The design uses `Workflow` for the logical automation and `WorkflowVersion` for saved JSON definitions. Connectors provide capabilities; workflows consume them without connector-specific logic in the workflow engine.

## Repository Layout

```text
backend/       FastAPI API, SQLAlchemy models, connector adapters, and tests
frontend/      React 19 + Vite application
docs/          Architecture, domain, workflow, and module specifications
Research/      Workflow research and supporting references
DevNotes/      Development notes
```

## Prerequisites

- Python 3.11 or newer
- Node.js 18 or newer and npm
- Docker Desktop (for PostgreSQL)

## Run Locally

### 1. Start PostgreSQL

From the backend directory:

```bash
cd backend
docker compose up -d postgres
```

The database is available at `localhost:5432` with database `sme_connect`, user `postgres`, and password `postgres`.

### 2. Start the API

Create and activate a virtual environment, then install the backend dependencies:

```bash
cd backend
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

Install and run FastAPI:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive API documentation is available at [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs).

### 3. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite prints the frontend URL, normally `http://localhost:5173`.

## Configuration

The backend reads settings from `backend/.env` when present. Defaults are suitable for local development:

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/sme_connect
JWT_SECRET_KEY=dev-insecure-secret-key-change-in-production-32bytes
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
EMAIL_VERIFICATION_EXPIRE_HOURS=24
```

Use a strong, private `JWT_SECRET_KEY` outside local development.

## Tests and Checks

Run backend tests from `backend/` with the virtual environment activated:

```bash
pytest
```

Run frontend checks from `frontend/`:

```bash
npm run lint
npm run build
```

## API Areas

- `/auth` - registration, login, verification, refresh, and current-user details
- `/organizations` - organizations, members, invitations, and roles
- `/connectors` - connector catalog and organization connections
- `/docs` - generated Swagger UI for the running API

## Product Documentation

- [`docs/01-project-scope.md`](docs/01-project-scope.md)
- [`docs/02-golden-workflow.md`](docs/02-golden-workflow.md)
- [`docs/03-architechture.md`](docs/03-architechture.md)
- [`docs/05-domain-model.md`](docs/05-domain-model.md)
- [`docs/module-1-user-organization.md`](docs/module-1-user-organization.md)
- [`docs/module-2-connectors.md`](docs/module-2-connectors.md)
- [`docs/module-3-workflows.md`](docs/module-3-workflows.md)