# Template 1: New Customer → CRM Lead

## 1. Basic Information

| Field | Value |
|---|---|
| **Name** | New Customer → CRM Lead |
| **Description** | Automatically create a CRM lead when a new customer is added to a Google Sheet. |
| **Category** | Sales |
| **Difficulty** | Beginner |
| **Industries** | Retail, Services |
| **Required Apps** | Google Sheets, CRM |

## 2. What the template actually does

```
Google Sheets
     │
     │ New Row
     ▼
┌──────────────────┐
│ Customer details │
│ Name             │
│ Email            │
│ Phone            │
└────────┬─────────┘
         │
         │ mapping
         ▼
┌──────────────────┐
│ CRM              │
│ Create Lead      │
└──────────────────┘
```

## 3. Trigger Definition
The template trigger is empty of configuration because the template doesn't know which Google Sheet belongs to the user. The user will choose that during guided setup.

```json
{
  "connector": "google_sheets",
  "event": "new_row",
  "config": {}
}
```

## 4. Action Definition
The CRM capability expects name and email as required inputs. The mapping matches exactly with our expected workflow payload.

```json
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
```

## 5. Complete Template Definition

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

## 6. Setup Schema (Onboarding Requirements)
The template tells the onboarding wizard exactly what is required from the user before this workflow can run.

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

*(Note: We will decide later whether `connection_resource` renders as a dropdown selector or a simple text input for a Spreadsheet ID depending on our Google Sheets connector capabilities.)*
