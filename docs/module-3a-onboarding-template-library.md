# Module 3A: Onboarding & Guided Template Library

## 1. Purpose
This module directly targets the research finding that SMEs don't struggle with cost as much as with *not knowing where to start*. This module eliminates the "blank canvas" overwhelm by providing a library of pre-built starter templates and a guided setup wizard.

## 2. Scope
This module covers:
- The Template Gallery (categorized, searchable list of blueprints).
- The Guided Setup Wizard (dynamic form to capture required user configuration).
- The Template-to-Workflow Engine (instantiating a real workflow from a template blueprint).

It explicitly does **not** cover:
- Template Versioning (MVP assumes templates are implicitly current).
- A separate execution engine (all templates become standard Workflows).

## 3. Template vs Workflow
This distinction is fundamental to the architecture.

**Template**
A reusable blueprint maintained by SME Connect.
- Name, Description, Category
- Apps required (`app_slugs`)
- Setup requirements (`setup_schema`)
- Workflow definition blueprint (`definition`)

**Workflow**
A user's actual automation created from that template.
- Organization, Owner
- User configuration (Connections, Mappings)
- Version history
- Execution history

Once a Workflow is created via the "Use Template" wizard, it is independent of the Template. Editing the Template later will not silently modify existing user Workflows.

## 4. Template Data Model
The database model for a Template in the MVP:

```json
{
  "id": 1,
  "name": "New Customer → CRM Lead",
  "description": "Create a CRM lead whenever a new customer is added to Google Sheets.",
  "category": "sales",
  "difficulty": "beginner",
  "industry_tags": ["retail", "services"],
  "app_slugs": ["google_sheets", "crm"],
  "definition": {},
  "setup_schema": {},
  "is_active": true,
  "created_at": "2026-10-01T12:00:00Z",
  "updated_at": "2026-10-01T12:00:00Z"
}
```

## 5. Template Definition
The `definition` field uses the exact same `WorkflowDefinition` structure established in Module 3. We are reusing the workflow definition rather than inventing a new TemplateDefinition language.

```json
{
  "trigger": {
    "connector": "google_sheets",
    "event": "new_row",
    "config": {}
  },
  "steps": [
    {
      "id": "create-lead",
      "type": "action",
      "connector": "crm",
      "action": "create_lead",
      "config": {},
      "mapping": {
        "name": "trigger.values.Name",
        "email": "trigger.values.Email",
        "phone": "trigger.values.Phone"
      }
    }
  ]
}
```

## 6. Setup Schema
The `setup_schema` dictates what information the Guided Wizard needs from the user. It is capability-driven.

```json
{
  "fields": [
    {
      "key": "spreadsheet",
      "label": "Customer Spreadsheet",
      "type": "connection_resource",
      "connector": "google_sheets",
      "required": true
    },
    {
      "key": "worksheet",
      "label": "Worksheet",
      "type": "text",
      "required": true
    }
  ]
}
```

The UI reads this schema and dynamically renders the appropriate selectors without hardcoding template-specific logic.

## 7. Template Lifecycle
For the MVP, lifecycle is binary:
- **ACTIVE:** Visible in the template gallery and available for new workflows.
- **INACTIVE:** Not available for new workflows. Existing workflows created from it remain untouched.

## 8. Template → Workflow Conversion
When a user completes the Guided Wizard, their answers are merged into the template's `definition`.

**Template Blueprint:** `spreadsheet = null, worksheet = null`
**User Setup:** `spreadsheet = "Customer Leads", worksheet = "Customers"`

**Configured WorkflowDefinition:**
```json
{
  "trigger": {
    "connector": "google_sheets",
    "event": "new_row",
    "config": {
      "spreadsheet_id": "abc123",
      "worksheet": "Customers"
    }
  }
}
```
This output is passed to the existing Workflow validation and saving engine.

## 9. Template Provenance
To track the origin of a workflow without affecting execution, we add a nullable `template_id` to the `Workflow` model.
- `template_id = NULL`: Created from the blank canvas.
- `template_id = 1`: Created from Template ID 1.

## 10. Initial Template Catalog
The seed set of templates for the MVP:

**Template 1: New Customer → CRM Lead**
- Category: Sales
- Apps: Google Sheets → CRM
- Flow: New Row → Create Lead

**Template 2: New Customer → Accounting Contact**
- Category: Billing
- Apps: Google Sheets → Zoho Books (or similar)
- Flow: New Row → Create Contact

**Template 3: New CRM Lead → Notification**
- Category: Notifications
- Apps: CRM → Notification (Slack/Email/WhatsApp)
- Flow: New Lead → Send Notification

## 11. MVP Boundaries
- Templates are one-time blueprints. They do not maintain a live link to the workflows they spawn.
- No complex Template Versioning yet (implicitly current).
- No elaborate taxonomy; categories are limited to `sales`, `billing`, `operations`, `notifications`.
- Difficulty levels are UI metadata only (`beginner`, `intermediate`, `advanced`).

## 12. Future Extensions
- Template Versioning (tracking which version of a template a workflow was spawned from).
- `created_from_template` boolean helper flag.
- Community-contributed templates.
