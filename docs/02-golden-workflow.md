# For now need one workflow that can become a reference for others 
Google Sheets → CRM
```
Example:

A salesperson receives a customer enquiry and enters it into a spreadsheet.

Google Sheet

Name       Phone        Email
Rahul      987xxxxxxx   rahul@gmail.com

SME Connect detects the new row:

New row
   ↓
SME Connect
   ↓
Read:
Name
Phone
Email
   ↓
Map fields
   ↓
CRM
   ↓
Create Lead

Result:

CRM

Lead
Name: Rahul
Phone: 987xxxxxxx
Email: rahul@gmail.com

Why this is useful for the project:

It exercises almost the entire core system:

connector
trigger
workflow
mapping
execution
external API
execution status
logging
monitoring

Without requiring WhatsApp, billing, branching, or complicated business logic.
```

## FOR NOW, sticking with one workflow 
Google Sheets → CRM: New row → Create Lead 


### Final workflow 
```
1. Log in.

2. Create/access their organization.

3. Connect the selected source application.

4. Connect the selected destination application.

5. Create a workflow:

Trigger:
New row in Google Sheet

Action:
Create lead in CRM

6. Map:

Sheet Name  → CRM Name
Sheet Phone → CRM Phone
Sheet Email → CRM Email

7. Publish the workflow.

8. Add a new row to the spreadsheet.

9. SME Connect detects the event.

10. SME Connect executes the workflow.

11. The CRM receives the lead.

12. The user can see:

Execution
Status: SUCCESS

13. If the CRM request fails, the user can see:

Execution
Status: FAILED
Reason: ...
```