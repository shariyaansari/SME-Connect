# Module 2 — Connector / Integration Management

## 1. Purpose

The Connector layer manages external service integrations, secure credential storage, connection health monitoring, and schema discovery (triggers and actions) required by the workflow execution engine.

---

## 2. Architecture: Ports & Adapters (Hexagonal)

Every third-party service implements `BaseConnectorAdapter` (`backend/app/modules/connectors/adapters/base.py`):

```
┌──────────────────────────────────────────────────────────────┐
│                    Workflow Engine / API                     │
└──────────────────────────────┬───────────────────────────────┘
                               │
                ┌──────────────▼──────────────┐
                │    BaseConnectorAdapter     │
                └──────────────┬──────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Google Sheets   │  │       CRM        │  │    Custom API    │
│ (OAuth2/Service) │  │(HubSpot/API Key) │  │  (REST / Bearer) │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## 3. Supported Connectors (v1 Catalog)

| Connector | Slug | Category | Auth Type | Key Triggers | Key Actions |
|---|---|---|---|---|---|
| **Google Sheets** | `google_sheets` | Spreadsheets | OAuth 2.0 / Service Acc | `new_row` | `append_row`, `read_rows` |
| **CRM Integration** | `crm` | CRM | API Key | `new_lead`, `deal_stage_updated` | `create_lead`, `update_lead` |
| **Custom REST API** | `custom_api` | Developer Tools | Bearer / Custom | `webhook_received` | `http_request` |
| **WhatsApp Business** | `whatsapp` | Communication | Bearer Token | `message_received` | `send_template`, `send_text` |

---

## 4. Database Entities

### `connections`
| Field | Type | Purpose |
|---|---|---|
| `id` | Integer | Primary key |
| `organization_id` | Integer | FK referencing `organizations.id` (multi-tenant scope) |
| `connector_slug` | String(50) | Adapter identifier (`google_sheets`, `crm`, etc.) |
| `name` | String(150) | User-assigned connection display name |
| `auth_type` | String(30) | Authentication method (`api_key`, `oauth2`, `bearer`) |
| `config` | JSON | Non-sensitive settings (e.g. `spreadsheet_id`, `crm_provider`) |
| `credentials` | JSON | Secret keys and tokens (masked in API responses) |
| `status` | String(20) | Health status (`active`, `error`, `disconnected`) |
| `last_tested_at` | DateTime(tz) | Timestamp of most recent health check |
| `error_message` | Text | Error details if health check failed |
| `created_at` | DateTime(tz) | Creation timestamp |
| `updated_at` | DateTime(tz) | Last updated timestamp |

---

## 5. API Design

| Method | Endpoint | Access | Purpose |
|---|---|---|---|
| `GET` | `/connectors/catalog` | Public / Authed | Discover available connectors and configuration schemas |
| `GET` | `/connectors` | Viewer+ | List all connections for current organization |
| `GET` | `/connectors/{id}` | Viewer+ | Get connection details (credentials masked) |
| `POST` | `/connectors` | Admin / Editor | Create a new connection and run initial health check |
| `POST` | `/connectors/{id}/test` | Admin / Editor | Trigger live connection health check |
| `PUT` | `/connectors/{id}` | Admin / Editor | Update connection config or credentials |
| `DELETE` | `/connectors/{id}` | Admin / Editor | Remove connection |
