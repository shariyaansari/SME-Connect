# Module 8: Data Mapping & Transformation Layer

## 1. Purpose & Overview

In real-world business workflows, data formats produced by one application rarely match the input formats required by another. For example:
- A customer submits a form with `"first_name"` and `"last_name"`, but the CRM requires a single `"full_name"` field.
- A spreadsheet contains formatted currency strings (e.g., `"$1,250.00"`), but an invoicing or accounting app requires a clean float or integer (`1250.0`).
- A webhook payload provides timestamps in ISO-8601 (`"2026-10-12T14:30:00Z"`), while a notification service requires human-readable localized dates (`"October 12, 2026"`).

**Module 8** delivers the **Data Mapping & Transformation Layer** for SME Connect. It allows business users and admins to configure field-to-field mappings, template string interpolations, and structured transformations without writing custom code or modifying connector adapters.

### Key Capabilities
1. **Field-to-Field Mapping**: Seamless path resolution from trigger outputs and preceding step outputs.
2. **Template String Interpolation**: Dynamic text formatting using mustache-style syntax, e.g.:
   `"Dear {{trigger.values.FirstName}} {{trigger.values.LastName}}, your order {{steps.step-1.order_id}} is confirmed."`
3. **Pure Transformation Functions**: 13 built-in transformations covering text formatting, extraction, coercion, default fallbacks, and date parsing.
4. **DAG Validation**: Pre-publish validation ensuring backward compatibility, forbidding self/forward references, and enforcing schema rules.
5. **Interactive Mapping Preview API**: Real-time test evaluation endpoint allowing users to test mapping rules on sample payloads before publishing.
6. **Visual Workflow Builder Integration**: Intuitive UI with mode tabs (Static, Variable, Template, Transform) and live test preview drawer.

---

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────┐
│                   FRONTEND / WEB UI                   │
│                                                        │
│  [Action Step Configuration Modal]                     │
│   ├── Mode Selector: [Static | Variable | Template | Transform]
│   ├── Parameter Configuration (Concat, Format Date, etc.)│
│   └── Interactive Mapping Preview Drawer              │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
         GET /transforms/catalog   POST /mapping/preview
                │                        │
┌───────────────▼────────────────────────▼───────────────┐
│                   BACKEND API (FastAPI)                │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │ app.modules.transformations                      │  │
│  │   ├── engine.py (Pure transform functions)       │  │
│  │   ├── schemas.py (Pydantic models & catalog)     │  │
│  │   └── router.py (/transforms/catalog, /preview)  │  │
│  └───────────────────────┬──────────────────────────┘  │
│                          │                             │
│                          ▼                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ app.modules.executions.resolver                  │  │
│  │   ├── resolve_mapping()                          │  │
│  │   └── resolve_path()                             │  │
│  └───────────────────────┬──────────────────────────┘  │
│                          │                             │
│                          ▼                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │ app.modules.workflows.validation                 │  │
│  │   └── validate_mapping_expression() (DAG checks) │  │
│  └───────────────────────┬──────────────────────────┘  │
└──────────────────────────┼─────────────────────────────┘
                           ▼
┌────────────────────────────────────────────────────────┐
│              RUNTIME EXECUTION ENGINE                  │
│                                                        │
│  - executes workflow steps sequentially               │
│  - resolves static, template, & transform mappings     │
│  - supplies sanitized inputs to Connector Adapters     │
└────────────────────────────────────────────────────────┘
```

---

## 3. Supported Transformations Catalog

Module 8 provides 13 pure, deterministic transformation functions:

| Type | Name | Category | Parameters | Example Usage |
|---|---|---|---|---|
| `concat` | Concatenate Strings | Text | `sources` (list), `separator` (optional string) | Combines first & last names with separator: `{"transform": "concat", "sources": ["trigger.first", "trigger.last"], "separator": " "}` |
| `trim` | Trim Whitespace | Text | `source` (string/path) | Strips leading/trailing spaces: `{"transform": "trim", "source": "trigger.raw_email"}` |
| `uppercase` | Uppercase Text | Text | `source` (string/path) | Converts text to uppercase: `{"transform": "uppercase", "source": "trigger.country"}` |
| `lowercase` | Lowercase Text | Text | `source` (string/path) | Normalizes emails: `{"transform": "lowercase", "source": "trigger.email"}` |
| `titlecase` | Title Case | Text | `source` (string/path) | Capitalizes words: `{"transform": "titlecase", "source": "trigger.city"}` |
| `replace` | Replace Substring | Text | `source`, `find`, `replace_with` (optional) | Removes prefixes: `{"transform": "replace", "source": "trigger.phone", "find": "+91-", "replace_with": ""}` |
| `substring` | Extract Substring | Text | `source`, `start`, `end` or `length` | Slices text: `{"transform": "substring", "source": "trigger.code", "start": 0, "length": 4}` |
| `default_value` | Default Fallback Value | Utility | `source`, `default` (any) | Fallback if empty/null: `{"transform": "default_value", "source": "trigger.phone", "default": "N/A"}` |
| `to_string` | Convert to String | Coercion | `source` (any), `default` (optional) | Coerces to string: `{"transform": "to_string", "source": "trigger.zip_code"}` |
| `to_number` | Convert to Number (Float) | Coercion | `source` (any), `default` (optional float) | Cleans currency & converts to float: `{"transform": "to_number", "source": "trigger.price", "default": 0.0}` |
| `to_integer` | Convert to Integer | Coercion | `source` (any), `default` (optional int) | Rounds/cleans to integer: `{"transform": "to_integer", "source": "trigger.quantity", "default": 1}` |
| `to_boolean` | Convert to Boolean | Coercion | `source` (any), `default` (optional bool) | Parses `"true"`, `"yes"`, `"1"`, `0`: `{"transform": "to_boolean", "source": "trigger.subscribed"}` |
| `format_date` | Format Date & Time | Date | `source`, `output_format`, `input_format` (optional) | Formats date strings: `{"transform": "format_date", "source": "trigger.created_at", "output_format": "%B %d, %Y"}` |

---

## 4. Template String Interpolation Engine

Template strings enable intuitive text composition using mustache-style variables `{{ ... }}`.

### Syntax
- `{{trigger.<path>}}`: Accesses fields from the trigger payload (e.g. `{{trigger.values.Email}}`).
- `{{steps.<step_id>.<path>}}`: Accesses outputs of preceding steps (e.g. `{{steps.crm_lead.id}}`).

### Runtime Evaluation Rules
1. Variables are extracted and evaluated dynamically using runtime execution context.
2. If a variable resolves to `None` or a missing key, it safely evaluates to an empty string (`""`) without crashing the workflow step.
3. Multiple placeholders can be mixed with arbitrary static text:
   `"Welcome {{trigger.values.FirstName}}! Your ticket #{{steps.zendesk.ticket_id}} was created on {{steps.zendesk.created_at}}."`

---

## 5. API Specifications

### 5.1 Transformation Catalog Endpoint
- **Method / Path**: `GET /workflows/transforms/catalog`
- **Auth**: Bearer token required.
- **Description**: Returns all supported transformations, descriptions, parameter requirements, and schema examples.
- **Response**: Array of `TransformationCatalogItem`.

### 5.2 Interactive Mapping Preview Endpoint
- **Method / Path**: `POST /workflows/mapping/preview`
- **Auth**: Bearer token required.
- **Request Body**:
  ```json
  {
    "mapping": {
      "full_name": {
        "transform": "concat",
        "sources": ["trigger.values.FirstName", " ", "trigger.values.LastName"]
      },
      "greeting": "Hello {{trigger.values.FirstName}}!",
      "status_upper": {
        "transform": "uppercase",
        "source": "trigger.values.Status"
      },
      "missing_phone": {
        "transform": "default_value",
        "source": "trigger.values.Phone",
        "default": "N/A"
      }
    },
    "sample_context": {
      "trigger": {
        "values": {
          "FirstName": "Sarah",
          "LastName": "Connor",
          "Status": "active"
        }
      }
    }
  }
  ```
- **Response (200 OK)**:
  ```json
  {
    "output": {
      "full_name": "Sarah Connor",
      "greeting": "Hello Sarah!",
      "status_upper": "ACTIVE",
      "missing_phone": "N/A"
    },
    "fields_evaluated": 4,
    "success": true,
    "errors": []
  }
  ```

---

## 6. Validation & DAG Data Flow Rules

During workflow draft validation and pre-publish checks (`validate_workflow_definition`):
1. **DAG Path Reference Validation**:
   - Every variable referenced in a template `{{...}}` or transformation `source` must begin with `trigger.` or `steps.<step_id>.`.
   - Forward references (referencing steps that have not yet executed) are rejected with error code `INVALID_STEP_REFERENCE`.
   - Self references (a step referencing its own output) are rejected with error code `SELF_REFERENCE_MAPPING`.
2. **Transformation Parameter Validation**:
   - Transform types must match `VALID_TRANSFORMATION_TYPES`.
   - `concat` requires a non-empty `sources` array.
   - `replace` requires both `source` and `find`.
   - `default_value` requires both `source` and `default`.
3. **Backward Compatibility**:
   - Simple string path mappings (`"name": "trigger.values.Name"`) remain 100% valid.
   - Static string literals without `{{` or `trigger.` pass through untouched.

---

## 7. Frontend Integration

In `frontend/src/components/WorkflowsView.jsx`:
1. **Action Step Modal Redesign**:
   - Expanded modal width (580px) to provide ample room for mapping and transform configuration.
   - Per-field mode switcher: `[Static]` `[Variable]` `[Template]` `[Transform]`.
2. **Dynamic Parameter Inputs**:
   - `concat`: Dynamic multi-item source builder with `+ Add Source` and separator input.
   - `replace`, `substring`, `default_value`, `format_date`: Contextual parameter fields.
   - Template editor with quick variable insert chips.
3. **Interactive Preview Panel**:
   - Collapsible panel in the Action Modal.
   - Pre-populated realistic sample context with "Reset Sample" option.
   - Real-time execution via `api.previewMapping()`.
   - Tabular preview display showing evaluated values and success badges.

---

## 8. Verification & Test Suite

The test suite in `backend/tests/test_module8_data_mapping.py` validates:
- All 13 pure transformation functions with edge cases (null values, missing keys, currency strings, dates).
- Template string interpolation engine with single and multiple variables.
- Backward compatibility of the execution resolver (`resolve_mapping`).
- Workflow validation rules (forward reference rejection, self-reference rejection, invalid transform types).
- Catalog (`GET /workflows/transforms/catalog`) and preview (`POST /workflows/mapping/preview`) API endpoints.
- End-to-end workflow execution with transformed action inputs (`execute_workflow`).

**Test Results**:
- `test_module8_data_mapping.py`: **19 / 19 passed**
- Full backend test suite: **179 / 179 passed** (0 regressions)
- Frontend production build: **Passed cleanly (`npm run build`)**
