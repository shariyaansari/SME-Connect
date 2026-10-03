# Module 3: Workflow Management

## 1. Purpose

The Workflow module lets an organization create, configure, validate, save,
publish, pause, and version automation workflows.

A workflow describes:

- one trigger
- one or more actions
- optional conditions
- step configuration
- field mappings between steps

The workflow engine is connector-agnostic. Connectors expose capabilities;
workflows consume those capabilities. Connector-specific behavior belongs in
the connector adapter, not in the workflow engine.

## 2. Scope and Terminology

### Workflow

`Workflow` is the logical identity of an automation. It belongs to exactly one
organization and can have multiple saved versions.

### WorkflowVersion

`WorkflowVersion` is a saved workflow definition. Its `definition` field stores
the structured definition as JSONB.

There is no separate `WorkflowDefinition` entity or database table.

Conceptually:

```text
Organization
    |
    +-- Workflow
            |
            +-- WorkflowVersion 1
            |       +-- definition JSONB
            |
            +-- WorkflowVersion 2
                    +-- definition JSONB
```

Only the published version is eligible for automatic execution. Editing a
workflow creates or updates a draft version without changing the currently
published version.

## 3. Workflow Lifecycle

The MVP supports these statuses:

| Status | Meaning |
| --- | --- |
| `draft` | The workflow is being created or edited. It is not executed automatically. |
| `published` | The workflow has passed validation and is active for execution. |
| `paused` | The workflow remains configured but does not execute automatically. |

Publishing must validate the selected version before it becomes active. Pausing
must stop automatic execution without deleting the workflow or its versions.

The exact versioning policy must preserve these invariants:

1. A workflow has at most one active published version.
2. Publishing a new version makes the previous published version inactive.
3. A draft cannot be executed automatically.
4. Historical versions remain readable after a newer version is published.

## 4. Workflow Definition

The definition is connector-agnostic JSON. Connector IDs, capability IDs, and
configuration values are data supplied by the connector registry and adapter.

Example:

```json
{
  "trigger": {
    "connector": "google_sheets",
    "event": "new_row",
    "config": {
      "spreadsheet_id": "example-sheet",
      "worksheet": "Leads"
    }
  },
  "steps": [
    {
      "id": "create-lead",
      "type": "action",
      "connector": "crm",
      "action": "create_lead",
      "config": {},
      "mapping": {
        "name": "trigger.row.name",
        "phone": "trigger.row.phone",
        "email": "trigger.row.email"
      }
    }
  ]
}
```

The engine must not contain connector-specific branches such as `if Google
Sheets` or `if CRM`. Adding a connector should require registering its
capabilities and implementing its adapter, not rewriting the workflow engine.

### 4.1 Definition Rules

- `trigger` is required and contains exactly one trigger capability.
- `steps` is required and contains one or more ordered steps.
- Every step has a stable, unique `id` within the definition.
- Every step has a supported `type` and references a registered capability.
- Configuration is validated by the referenced connector capability.
- Mappings reference fields from the trigger or an earlier step.
- The definition must be serializable JSON and must not contain secrets.

## 5. Step Types

The MVP supports three step types:

| Type | Purpose | Example |
| --- | --- | --- |
| `trigger` | Starts a workflow when an event occurs. | Google Sheets: `new_row` |
| `action` | Performs an operation through a connector. | CRM: `create_lead` |
| `condition` | Controls whether subsequent steps execute. | `status = qualified` |

The top-level `trigger` is the workflow entry point. A `trigger` step should
not also appear in the ordered `steps` array unless the schema explicitly
defines that representation. The MVP should use one representation
consistently.

## 6. Connector Capability Discovery

The workflow builder obtains available connectors, their supported triggers, actions,
and field schemas dynamically from the Connector Registry, correlated with the active
organization's configured connections.

```text
Connector Registry
    │
    ├── Google Sheets
    │     ├── Trigger: new_row ──> payload_schema (row_index, values, created_at)
    │     └── Action: append_row ──> input_schema (values [required])
    │
    └── CRM
          ├── Trigger: new_lead ──> payload_schema (lead_id, name, email, phone, status)
          └── Action: create_lead ──> input_schema (name [req], email [req], phone, company)
```

### 6.1 Endpoints

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/workflows/capabilities` | Viewer+ | Return all connector capabilities with organization connection status and field schemas |
| `GET` | `/workflows/capabilities/{slug}` | Viewer+ | Return capabilities and connection availability for a specific connector |

### 6.2 Security and Availability Guarantees

1. **Credentials Never Exposed**: Capability endpoints return `OrganizationConnectionSummary` (`id`, `name`, `status`, `created_at`, `last_tested_at`). Secret keys, auth tokens, passwords, and `masked_credentials` are strictly omitted.
2. **Organization Scoped**: A tenant only sees connections belonging to their active organization (`Connection.organization_id == membership.organization_id`). Cross-tenant connection visibility is impossible.
3. **Dynamic Registry Resolution**: No connector slugs or capability names are hardcoded in the workflow engine or UI views. All options and mapping fields flow dynamically from adapter metadata.

## 7. Validation

Validation occurs before publishing and should also be available while saving
a draft. At minimum, validation checks:

- required trigger and steps are present
- all IDs are unique and well-formed
- referenced connectors and capabilities exist
- step configuration matches the capability schema
- mappings reference available fields
- mappings use compatible source and destination types where metadata exists
- required connector connections are available to the organization
- conditions have a valid expression and operands
- the definition contains no unsupported step types or unknown fields

Validation should return actionable, field-level errors so the workflow builder
can show the user which step or property needs attention.

## 8. API Design and Persistence Scope

### 8.1 Endpoint Specifications

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `POST` | `/workflows` | Admin / Editor | Create workflow in `draft` status with initial `version_number=1` |
| `GET` | `/workflows` | Viewer+ | List all workflows for the authenticated user's organization |
| `GET` | `/workflows/{id}` | Viewer+ | Retrieve workflow details & definition (default: latest version; `?version=N`) |
| `PUT` | `/workflows/{id}` | Admin / Editor | Update metadata or definition |
| `DELETE` | `/workflows/{id}` | Admin / Editor | Delete workflow and cascade delete all version records |

### 8.2 Security Boundary & Multi-Tenancy Invariant

The client does **not** provide `?organization_id=` in CRUD requests. The organization is a strict security boundary resolved internally from the authenticated user:

```text
current_user (JWT) ──> active membership ──> organization_id
```

Cross-organization requests are rejected with `404 Not Found`.

### 8.3 Metadata vs. Definition Updates (`PUT /workflows/{id}`)

1. **Metadata Updates** (`name`, `description`):
   - Modifies the `Workflow` entity directly.
   - Does **not** create or touch versions.
2. **Definition Updates** (`definition`):
   - Runs full connector-agnostic validation before write.
   - If the current workflow is an unpublished draft, updates the draft version in-place.
   - If the current workflow was previously published (`published_at is not None`), spawns a new draft version (`version_number = latest + 1`) and sets workflow status back to `draft`.

### 8.4 Publish & Pause Lifecycle

#### State Machine

```text
             ┌─────────────┐
             │    DRAFT    │
             └──────┬──────┘
                    │
                 publish
                    │
                    ▼
             ┌─────────────┐
             │  PUBLISHED  │
             └──────┬──────┘
                    │
                  pause
                    │
                    ▼
             ┌─────────────┐
             │   PAUSED    │
             └─────────────┘
```

#### Endpoints

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `POST` | `/workflows/{id}/publish` | Admin / Editor | Dual-mode: publishes latest draft version, or resumes existing published version if paused |
| `POST` | `/workflows/{id}/pause` | Admin / Editor | Pauses a `published` workflow without touching definition or versions |

#### Dual Semantics of `POST /workflows/{id}/publish`

The `/publish` endpoint intentionally serves two distinct lifecycle operations depending on current workflow state:

1. **`Draft` + `/publish` $\longrightarrow$ Publish latest draft version:**
   - Validates the draft definition.
   - Verifies active connections for all referenced connectors.
   - Stamps `published_at = now()`.
   - Transitions `status` to `published` with `is_active: True`.
   - Supersedes any previous published version.

2. **`Paused` + `/publish` $\longrightarrow$ Resume existing published version:**
   - Re-verifies active connections for all referenced connectors.
   - Restores `status` to `published` with `is_active: True`.
   - Does **not** create a new version or alter definition; historical `published_at` is preserved.

#### Invariants and Preconditions

1. **Validation & Connection Availability:**
   - Full semantic validation (`validate_workflow_or_raise`) runs prior to publication.
   - Every connector referenced by the trigger or action steps must have an active connection (`status == "active"`) in the calling organization.
   - If any connection is missing or in `error` status, publication is rejected with `400 Bad Request`.
2. **Version Publication:**
   - Target version receives `published_at = now()` (if unpublished).
   - Workflow status transitions to `published`.
   - Critical Invariant: **Published active versions $\le 1$**. Only the newly published version has `is_active: True`.
   - Historical versions are **never** deleted. Their timestamps and definitions remain preserved in `workflow_versions`.
3. **Pausing:**
   - Requires current status to be `published`. Calling pause on `draft` or `paused` yields `400 Bad Request`.
   - Transitions status to `paused`. All version definitions and publication timestamps remain untouched.
   - Calling `POST /workflows/{id}/publish` on a paused workflow resumes execution eligibility.

### 8.5 Version Immutability Invariant

**Central Rule:** *Once a `WorkflowVersion` has been published (`published_at is not None`), its definition can never be modified.*

```text
V1 Draft ✏️
   │
   │ POST /publish
   ▼
V1 Published 🔒  <── Immutable forever
   │
   │ PUT /workflows/{id}
   ▼
V2 Draft ✏️
   │
   │ POST /publish
   ▼
V2 Published 🔒  <── Active published version (V1 remains unchanged in history)
```

#### Multi-Level Protection:

1. **Service / API Level:**
   - Calling `PUT /workflows/{id}` on a published workflow automatically protects the published version by spawning a new draft version (`version_number = latest + 1`).
   - Explicitly targeting a published version (`PUT /workflows/{id}?version=1`) is rejected with `400 Bad Request ("Cannot modify version 1: Published workflow versions are immutable")`.
2. **Database / ORM Level:**
   - A SQLAlchemy `before_update` event listener (`check_workflow_version_immutability`) monitors the `WorkflowVersion` model. Any attempt to modify `version.definition` on an already-published record raises a `ValueError` prior to database write.
3. **Historical Readability:**
   - Historical versions remain fully readable at any time via `GET /workflows/{id}?version=N`.
   - Default query (`GET /workflows/{id}`) resolves to the latest version.
   - The version list in detail responses surfaces all historical versions alongside `published_at` and `is_active` flags.

## 9. Golden Workflow

The first end-to-end workflow is intentionally small:

```text
Google Sheets: New Row
        |
        v
Map Name, Phone, and Email
        |
        v
CRM: Create Lead
```

User journey:

1. Sign in and access an organization.
2. Connect Google Sheets as the source application.
3. Connect the CRM as the destination application.
4. Create a workflow with a Google Sheets `new_row` trigger.
5. Map `Name`, `Phone`, and `Email` to the CRM lead fields.
6. Validate and publish the workflow.
7. Add a row to the spreadsheet.
8. The trigger detects the event and the execution layer runs the published version.
9. The CRM receives the lead.
10. The user can inspect the execution result.

The workflow module owns the definition and publication boundary. Trigger
detection, execution, retries, and execution reporting belong to their
respective future modules.

## 10. Example Definitions

These examples describe supported use cases; they are not hardcoded workflows.

```text
Google Sheets: New Row
    -> CRM: Create Lead

CRM: New Lead
    -> WhatsApp: Send Message

Stripe: Payment Succeeded
    -> Google Sheets: Append Row

Google Sheets: New Row
    -> Condition: Status = Qualified
    -> CRM: Create Lead
    -> WhatsApp: Send Notification
```

## 11. Module Boundaries

Module 3 is responsible for workflow identity, versions, definitions,
validation, and publication state.

The following are intentionally outside the initial workflow-management MVP:

- trigger polling and webhook handling
- execution orchestration
- retries, queues, and dead-letter handling
- execution monitoring and detailed execution history
- advanced branching and parallel execution

Those capabilities may consume published workflow versions in later modules.

## 12. Implementation Order

1. Add the `Workflow` database model.
2. Add the `WorkflowVersion` model and JSONB definition storage.
3. Define the workflow schema and validation errors.
4. Implement organization-scoped CRUD APIs.
5. Implement connector capability discovery.
6. Implement publish and pause transitions.
7. Implement version handling and immutable historical versions.
8. Build the dynamic workflow builder UI.
9. Complete the Google Sheets to CRM golden workflow end to end.

Each step should be covered by focused API, validation, authorization, and
versioning tests before the next integration surface is added.