# Template 2: New Customer → Accounting Contact

## 1. Basic Information

| Field | Value |
|---|---|
| **Name** | New Customer → Accounting Contact |
| **Description** | Automatically create an accounting contact when a new customer is added to Google Sheets. |
| **Category** | Billing |
| **Difficulty** | Beginner |
| **Industries** | Retail, Services |
| **Required Apps** | Google Sheets, Zoho Books |

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
│ Zoho Books       │
│ Create Contact   │
└──────────────────┘
```

## 3. Trigger Definition
Like Template 1, the spreadsheet is supplied by the user during the guided setup.

```json
{
  "connector": "google_sheets",
  "event": "new_row",
  "config": {}
}
```

## 4. Action Definition
Based on the `zoho_books` connector capability model, the `create_contact` action expects `contact_name` (required), `email`, and `phone`.

```json
{
  "id": "create-contact",
  "type": "action",
  "connector": "zoho_books",
  "action": "create_contact",
  "config": {},
  "mapping": {
    "contact_name": "trigger.values.Name",
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
      "id": "create-contact",
      "type": "action",
      "connector": "zoho_books",
      "action": "create_contact",
      "config": {},
      "mapping": {
        "contact_name": "trigger.values.Name",
        "email": "trigger.values.Email",
        "phone": "trigger.values.Phone"
      }
    }
  ]
}
```

## 6. Setup Schema (Onboarding Requirements)
The wizard requires the exact same Google Sheets configuration as Template 1.

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
