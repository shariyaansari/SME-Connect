# Frontend

React

Because the workflow builder is highly interactive and component-driven.

# Backend

Python + FastAPI

Because the backend is an API/orchestration layer, with future AI-assisted workflow generation as a planned extension.

# Database

PostgreSQL

Because SME Connect has strong relational requirements:

Users
Organizations
Memberships
Roles
Connections
Workflows
Executions
Logs

## while PostgreSQL's JSONB support handles flexible workflow definitions.

---

Future AI
```
Python ecosystem

Potentially used for:

Natural language
       ↓
Workflow suggestion
       ↓
Workflow definition
       ↓
Human approval
       ↓
Execution
```


## Architechture with final tech stack 

```
                    ┌──────────────┐
                    │    React     │
                    │   Frontend   │
                    └──────┬───────┘
                           │
                        HTTP/API
                           │
                           ▼
                    ┌──────────────┐
                    │   FastAPI    │
                    │   Backend    │
                    └──────┬───────┘
                           │
        ┌──────────────────┼───────────────────┐
        │                  │                   │
        ▼                  ▼                   ▼
   Workflows          Execution           Connectors
   Triggers           Engine              / Adapters
   Mapping            Monitoring
        │                  │                   │
        └──────────────────┼───────────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ PostgreSQL   │
                    │ + JSONB      │
                    └──────────────┘