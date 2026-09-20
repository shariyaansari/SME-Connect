                         ┌──────────────┐
                         │     User     │
                         └──────┬───────┘
                                │
                                │ membership
                                ▼
                         ┌──────────────┐
                         │ Organization │
                         └──────┬───────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
       ┌────────────┐    ┌────────────┐    ┌─────────────┐
       │ Connection │    │  Workflow  │    │ Audit Log   │
       └────────────┘    └─────┬──────┘    └─────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Workflow Version│
                       └────────┬────────┘
                                │
                     ┌──────────┴──────────┐
                     │                     │
                     ▼                     ▼
                 ┌─────────┐          ┌────────┐
                 │ Trigger │          │ Action │
                 └─────────┘          └───┬────┘
                                          │
                                      Mapping
                                          │
                                          ▼
                                  ┌──────────────┐
                                  │  Execution   │
                                  └──────┬───────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │Execution Step│
                                  └──────────────┘

## Repository check 

### Top-level project
```
sme-connect/
│
├── frontend/
│
├── backend/
│
├── docs/
│
├── .gitignore
├── README.md
└── docker-compose.yml      
```

### Frontend

We know React is responsible for the user experience.

```
frontend/
│
├── src/
│   │
│   ├── components/
│   │
│   ├── pages/
│   │
│   ├── features/
│   │
│   ├── services/
│   │
│   ├── hooks/
│   │
│   ├── layouts/
│   │
│   ├── types/
│   │
│   └── app/
│
├── public/
└── package.json
```
### Backend

We know React is responsible for the user experience.

```
modules/
│
├── auth/
│
├── organizations/
│
├── connectors/
│
├── workflows/
│
├── triggers/
│
├── execution/
│
├── monitoring/
│
└── audit/
```

### Database

We'll keep database setup separate:

```
backend/app/database/
├── session.py
├── base.py
└── migrations/
```
The exact migration tooling can be decided when we actually set up PostgreSQL.
we'll use Alembic alongside SQLAlchemy.

### Tests

```
backend/tests/
│
├── auth/
├── organizations/
├── connectors/
├── workflows/
└── execution/
```


