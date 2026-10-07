# Module 2 — Connector / Integration Management

## 1. Purpose

The Connector layer manages external service integrations, secure credential storage with encryption at rest, connection health monitoring, schema discovery (triggers and actions), and data read/action execution contracts required by the workflow execution engine.

---

## 2. Architecture: Ports & Adapters (Hexagonal)

Every third-party service implements `BaseConnectorAdapter` (`backend/app/modules/connectors/adapters/base.py`):

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Workflow Engine / Orchestrator                       │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                     ┌──────────────▼──────────────┐
                     │    BaseConnectorAdapter     │
                     └──────────────┬──────────────┘
                                    │
       ┌──────────────┬─────────────┼──────────────┬─────────────┐
       ▼              ▼             ▼              ▼             ▼
┌─────────────┐ ┌──────────┐ ┌─────────────┐ ┌──────────┐ ┌─────────────┐
│Google Sheets│ │   CRM    │ │   Stripe    │ │Zoho Books│ │ Custom API  │
│  (Service)  │ │ (HubSpot)│ │  (Billing)  │ │ (Acctng) │ │  & WhatsApp │
└─────────────┘ └──────────┘ └─────────────┘ └──────────┘ └─────────────┘
```

---

## 3. Supported Connectors Catalog

| Connector | Slug | Category | Availability | Auth Type | Key Triggers | Key Actions |
|---|---|---|---|---|---|---|
| **Google Sheets** | `google_sheets` | Spreadsheets | **Available (MVP)** | OAuth 2.0 / Service Acc | `new_row` | `append_row`, `read_rows` |
| **CRM Integration** | `crm` | CRM | **Available (MVP)** | API Key | `new_lead`, `deal_stage_updated` | `create_lead`, `update_lead` |
| **Stripe Billing** | `stripe` | Billing & Invoicing | Coming soon (P1) | Bearer API Key | `invoice_payment_succeeded`, `charge_failed` | `create_customer_invoice`, `charge_customer` |
| **Zoho Books** | `zoho_books` | Accounting | Coming soon (P1) | OAuth 2.0 / Auth Token | `invoice_created`, `payment_received` | `record_invoice`, `create_customer` |
| **Custom REST API** | `custom_api` | Developer Tools | Coming soon (P1) | Bearer / Custom | `webhook_received` | `http_request` |
| **WhatsApp Business** | `whatsapp` | Communication | Planned (P1) | Bearer Token | `message_received` | `send_template`, `send_text` |

---

## 4. Credential Security & Encryption at Rest

1. **Fernet Symmetric Encryption**:
   - Connector secrets (`api_key`, `client_secret`, `access_token`, etc.) are encrypted before being written to the database using AES-128 CBC via `cryptography.fernet.Fernet`.
   - Fernet key is derived from `ENCRYPTION_SECRET_KEY` using SHA-256 base64 URL-safe encoding.
   - Stored in the DB `credentials` JSON column in the format: `{"_encrypted": "<ciphertext>"}`.
2. **Backward Compatibility**:
   - If a plain JSON dictionary is encountered during migration or testing, `decrypt_credentials` gracefully handles it without raising an error.
3. **Response Masking**:
   - Connection read endpoints (`GET /connectors`, `GET /connectors/{id}`) never expose plain secret credentials to the client.
   - Values are masked as `••••••••` or `sec_••••` to allow users to verify that a secret is saved without leaking plaintext.
4. **Execution Decryption**:
   - Only backend adapter execution methods (`test_connection`, `read_trigger_data`, `execute_action`) decrypt credentials in-memory for the duration of the external HTTP call.

---

## 5. Execution Contracts (Workflow Engine Bridge)

Each adapter extends `BaseConnectorAdapter` with uniform runtime contracts:

```python
class BaseConnectorAdapter(ABC):
    @abstractmethod
    def test_connection(self, config: dict, credentials: dict) -> ConnectionTestResult:
        """Runs a live diagnostic ping to verify connectivity and credential validity."""
        ...

    def read_trigger_data(
        self,
        trigger_slug: str,
        config: dict,
        credentials: dict,
        state: dict | None = None,
    ) -> tuple[list[dict], dict]:
        """Polls or fetches new trigger events since last state cursor. Returns (records, new_state)."""
        ...

    def execute_action(
        self,
        action_slug: str,
        config: dict,
        credentials: dict,
        input_data: dict,
    ) -> dict:
        """Executes a downstream action with the resolved workflow payload."""
        ...
```

---

## 6. Database Entities

### `connections`
| Field | Type | Purpose |
|---|---|---|
| `id` | Integer | Primary key |
| `organization_id` | Integer | FK referencing `organizations.id` (multi-tenant scope) |
| `connector_slug` | String(50) | Adapter identifier (`google_sheets`, `crm`, `stripe`, etc.) |
| `name` | String(150) | User-assigned connection display name |
| `auth_type` | String(30) | Authentication method (`api_key`, `oauth2`, `bearer`) |
| `config` | JSON | Non-sensitive settings (e.g. `spreadsheet_id`, `crm_provider`) |
| `credentials` | JSON | Encrypted secret envelope (`{"_encrypted": "..."}`) |
| `status` | String(20) | Health status (`active`, `error`, `disconnected`) |
| `last_tested_at` | DateTime(tz) | Timestamp of most recent health check |
| `error_message` | Text | Error details if health check failed |
| `created_at` | DateTime(tz) | Creation timestamp |
| `updated_at` | DateTime(tz) | Last updated timestamp |

---

## 7. API Design & Role-Based Access Control (RBAC)

| Method | Endpoint | Minimum Role | Purpose |
|---|---|---|---|
| `GET` | `/connectors/catalog` | Authenticated | Discover available connectors and schemas |
| `GET` | `/connectors` | Viewer | List all connections for current organization |
| `GET` | `/connectors/{id}` | Viewer | Get connection details (credentials masked) |
| `POST` | `/connectors` | Member / Admin | Create connection, encrypt credentials, run health test |
| `POST` | `/connectors/{id}/test` | Member / Admin | Trigger live diagnostic health test |
| `PUT` | `/connectors/{id}` | Member / Admin | Update connection config, re-encrypt credentials, re-test |
| `DELETE` | `/connectors/{id}` | Member / Admin | Disconnect and remove integration |

> [!NOTE]
> Viewers are restricted from creating, modifying, testing, or deleting connections both at the API level (returning `403 Forbidden`) and at the UI level (buttons disabled with explanatory tooltips).
