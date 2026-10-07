# Template 3: New CRM Lead → WhatsApp Notification

## 1. Basic Information

| Field | Value |
|---|---|
| **Name** | New CRM Lead → WhatsApp Notification |
| **Description** | Send a WhatsApp notification when a new lead is created in the CRM. |
| **Category** | Notifications |
| **Difficulty** | Beginner |
| **Industries** | Retail, Services |
| **Required Apps** | CRM, WhatsApp |

## 2. What the template actually does

```
CRM
 │
 │ New Lead
 ▼
┌──────────────────┐
│ Lead details     │
│ lead_id          │
│ name             │
│ email            │
│ phone            │
│ status           │
└────────┬─────────┘
         │
         │ mapping
         ▼
┌──────────────────┐
│ WhatsApp         │
│ Send Text        │
└──────────────────┘
```

## 3. Trigger Definition
Based on the `crm` connector capability model, the `new_lead` trigger exposes `lead_id`, `name`, `email`, `phone`, and `status`.

```json
{
  "connector": "crm",
  "event": "new_lead",
  "config": {}
}
```

## 4. Action Definition
Based on the `whatsapp` connector capability model, the `send_text` action expects `to_number` (required) and `text` (required).

We map the CRM `phone` to the WhatsApp `to_number`. Since our current mapping UI doesn't support complex string interpolation yet, we provide the static notification message in the `config` block, and the dynamic phone number in the `mapping` block.

```json
{
  "id": "send-notification",
  "type": "action",
  "connector": "whatsapp",
  "action": "send_text",
  "config": {
    "text": "New CRM lead received."
  },
  "mapping": {
    "to_number": "trigger.values.phone"
  }
}
```

## 5. Complete Template Definition

```json
{
  "trigger": {
    "connector": "crm",
    "event": "new_lead",
    "config": {}
  },
  "steps": [
    {
      "id": "send-notification",
      "type": "action",
      "connector": "whatsapp",
      "action": "send_text",
      "config": {
        "text": "New CRM lead received."
      },
      "mapping": {
        "to_number": "trigger.values.phone"
      }
    }
  ]
}
```

## 6. Setup Schema (Onboarding Requirements)
The onboarding wizard doesn't need to ask for a specific Google Sheet this time. It just needs the user to connect their CRM and WhatsApp accounts. However, if we wanted to allow them to customize the static notification message during setup, we could expose it in the setup schema:

```json
{
  "fields": [
    {
      "key": "message_text",
      "label": "Notification Message",
      "type": "text",
      "required": true,
      "default": "New CRM lead received."
    }
  ]
}
```
*(For the MVP, we can even leave the setup schema entirely empty and just rely on the pre-filled `config.text` in the template definition, allowing them to edit it in the standard workflow builder later).*
