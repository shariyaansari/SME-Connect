# Template Specification Catalog (3A.2 Complete)

The following tables define the complete specifications for the seed templates of SME Connect.

| Specification | Template 1 | Template 2 | Template 3 |
|---|---|---|---|
| **Name** | New Customer → CRM Lead | New Customer → Accounting Contact | New CRM Lead → WhatsApp Notification |
| **Description** | Automatically create a CRM lead when a new customer is added to a Google Sheet. | Automatically create an accounting contact when a new customer is added to Google Sheets. | Send a WhatsApp notification when a new lead is created in the CRM. |
| **Category** | Sales | Billing | Notifications |
| **Industry** | Retail, Services | Retail, Services | Retail, Services |
| **Apps** | Google Sheets, CRM | Google Sheets, Zoho Books | CRM, WhatsApp |
| **Trigger** | Google Sheets → New Row | Google Sheets → New Row | CRM → New Lead |
| **Action** | CRM → Create Lead | Zoho Books → Create Contact | WhatsApp → Send Text |
| **Required Action Fields** | `name`, `email` | `contact_name` | `to_number`, `text` |
| **Mappings** | `name` ← `trigger.values.Name`<br>`email` ← `trigger.values.Email`<br>`phone` ← `trigger.values.Phone` | `contact_name` ← `trigger.values.Name`<br>`email` ← `trigger.values.Email`<br>`phone` ← `trigger.values.Phone` | `to_number` ← `trigger.values.phone`<br>*(Message text is a static config)* |
| **Setup Fields** | `spreadsheet`, `worksheet` | `spreadsheet`, `worksheet` | *(None required, handled implicitly by connection)* |
