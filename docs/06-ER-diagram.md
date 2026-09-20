# 1. Entities 

From our domain model, we currently have:

User
Organization
Membership
Connection
Workflow
Workflow Version
Execution
Execution Step
Audit Log


```
┌────────────────────┐
│ users              │
└─────────┬──────────┘
          │
          │
┌─────────▼──────────┐
│ memberships        │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│ organizations      │
└─────┬──────────────┘
      │
      ├───────────────┐
      │               │
      ▼               ▼
┌────────────┐   ┌──────────────┐
│ connections│   │ workflows    │
└────────────┘   └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │workflow_     │
                 │versions      │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ executions   │
                 └──────┬───────┘
                        │
                        ▼
                 ┌──────────────┐
                 │execution_    │
                 │steps         │
                 └──────────────┘

organizations
      │
      ▼
 audit_logs

```

# 2. RelationShips and Cardinality 
| Relationship                 | Cardinality | Meaning                                                     |
| ---------------------------- | ----------- | ----------------------------------------------------------- |
| User → Membership            | 1 : Many    | One user can belong to multiple organizations               |
| Organization → Membership    | 1 : Many    | One organization can have multiple members                  |
| Organization → Connection    | 1 : Many    | An organization can connect multiple external apps/accounts |
| Organization → Workflow      | 1 : Many    | An organization can create multiple workflows               |
| Workflow → Workflow Version  | 1 : Many    | A workflow can have multiple saved versions                 |
| Workflow Version → Execution | 1 : Many    | One version can be executed many times                      |
| Execution → Execution Step   | 1 : Many    | One execution contains multiple steps                       |
| Organization → Audit Log     | 1 : Many    | An organization can have many audit events                  |
| User → Audit Log             | 1 : Many    | A user can generate many audit events                       |



```
User
 │
 ├── Membership ──> Organization
 │                       │
 │                       ├── Connections
 │                       ├── Workflows
 │                       │      │
 │                       │      └── Versions
 │                       │             │
 │                       │             └── Executions
 │                       │                    │
 │                       │                    └── Steps
 │                       │
 │                       └── Audit Logs
```

Then as we implement each module:

| Module                     | Design database as we reach it                      |
| -------------------------- | --------------------------------------------------- |
| **1. User & Organization** | `users`, `organizations`, `memberships`             |
| **2. Connectors**          | `connections`                                       |
| **3. Workflow Builder**    | `workflows`, `workflow_versions`                    |
| **4. Triggers**            | Extend workflow definition / related data if needed |
| **5. Execution**           | `executions`, `execution_steps`                     |
| **6. Error & Logging**     | Extend execution/log structure                      |
| **7. Monitoring**          | Mostly reads from execution data                    |
| **8. Data Mapping**        | Mostly part of workflow definition                  |


Before implementing each module, we'll do:

Understand → Design → Database → API → UI → Test