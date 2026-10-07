# Base Architechture 
```
                    ┌──────────────────┐
                    │      USER        │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Web Application│
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │   Backend API    │
                    └───────┬──────────┘
                            │
              ┌─────────────┼──────────────┐
              │             │              │
              ▼             ▼              ▼
        ┌──────────┐  ┌────────────┐  ┌─────────────┐
        │ Database │  │  Trigger / │  │  Connector  │
        │          │  │   Events   │  │    Layer    │
        └──────────┘  └─────┬──────┘  └──────┬──────┘
                             │                │
                             ▼                │
                      ┌──────────────┐        │
                      │   Workflow   │◄───────┘
                      │   Execution  │
                      │    Engine    │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │ Monitoring &  │
                      │ Error Logs   │
                      └──────────────┘

```

| Component                  | Responsibility                      |
| -------------------------- | ----------------------------------- |
| **Web Application**        | User interface                      |
| **Backend API**            | Application/business operations     |
| **Database**               | Persistent data                     |
| **Connector Layer**        | Communication with external apps    |
| **Trigger/Event Layer**    | Detect workflow-triggering events   |
| **Execution Engine**       | Run workflows                       |
| **Monitoring/Error Layer** | Record and expose execution results |

## Central Flow 
```
User
 ↓
Web App
 ↓
Backend
 ↓
Workflow Definition
 ↓
Trigger
 ↓
Execution Engine
 ↓
Connector
 ↓
External App
 ↓
Execution Result
 ↓
Database
 ↓
Dashboard
```



# High Level Architechture 
We'll have 3 main runtime parts initially: 
1. Frontend
2. Backend
3. Database
```
                         ┌──────────────────────┐
                         │        USER          │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   FRONTEND / WEB UI  │
                         │                      │
                         │ Dashboard            │
                         │ Connections          │
                         │ Workflow Builder     │
                         │ Execution History    │
                         │ Settings             │
                         └──────────┬───────────┘
                                    │
                              HTTP / HTTPS
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────┐
│                     BACKEND APPLICATION                  │
│                                                          │
│  ┌────────────┐     ┌──────────────┐                    │
│  │ Auth &     │     │ Organization │                    │
│  │ RBAC       │     │ & Users      │                    │
│  └────────────┘     └──────────────┘                    │
│                                                          │
│  ┌────────────┐     ┌──────────────┐                    │
│  │ Workflow   │     │ Data Mapping │                    │
│  │ Management │     │              │                    │
│  └────────────┘     └──────────────┘                    │
│                                                          │
│  ┌────────────┐     ┌──────────────┐                    │
│  │ Trigger /  │────►│ Execution    │                    │
│  │ Events     │     │ Engine       │                    │
│  └────────────┘     └──────┬───────┘                    │
│                             │                            │
│  ┌────────────┐             │     ┌──────────────┐      │
│  │ Monitoring │◄────────────┘     │ Connectors   │──────┼──► Google Sheets
│  │ & Errors   │                   │              │──────┼──► CRM
│  └────────────┘                   └──────────────┘      │
│                                                          │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
                   ┌──────────────────┐
                   │     DATABASE     │
                   │                  │
                   │ Users            │
                   │ Organizations    │
                   │ Connections      │
                   │ Workflows        │
                   │ Executions       │
                   │ Logs             │
                   └──────────────────┘
```

