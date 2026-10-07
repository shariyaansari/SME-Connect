import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import Template

logger = logging.getLogger(__name__)

INITIAL_TEMPLATES = [
    {
        "name": "New Customer → CRM Lead",
        "description": "Automatically create a CRM lead when a new customer is added to a Google Sheet.",
        "category": "Sales",
        "difficulty": "Beginner",
        "industry_tags": ["Retail", "Services"],
        "app_slugs": ["google_sheets", "crm"],
        "is_active": True,
        "definition": {
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
        },
        "setup_schema": {
            "fields": [
                {
                    "key": "spreadsheet",
                    "label": "Customer Spreadsheet",
                    "type": "connection_resource",
                    "connector": "google_sheets",
                    "required": True
                },
                {
                    "key": "worksheet",
                    "label": "Worksheet",
                    "type": "text",
                    "required": True
                }
            ]
        }
    },
    {
        "name": "New Customer → Accounting Contact",
        "description": "Automatically create an accounting contact when a new customer is added to Google Sheets.",
        "category": "Billing",
        "difficulty": "Beginner",
        "industry_tags": ["Retail", "Services"],
        "app_slugs": ["google_sheets", "zoho_books"],
        "is_active": True,
        "definition": {
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
        },
        "setup_schema": {
            "fields": [
                {
                    "key": "spreadsheet",
                    "label": "Customer Spreadsheet",
                    "type": "connection_resource",
                    "connector": "google_sheets",
                    "required": True
                },
                {
                    "key": "worksheet",
                    "label": "Worksheet",
                    "type": "text",
                    "required": True
                }
            ]
        }
    },
    {
        "name": "New CRM Lead → WhatsApp Notification",
        "description": "Send a WhatsApp notification when a new lead is created in the CRM.",
        "category": "Notifications",
        "difficulty": "Beginner",
        "industry_tags": ["Retail", "Services"],
        "app_slugs": ["crm", "whatsapp"],
        "is_active": True,
        "definition": {
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
        },
        "setup_schema": {
            "fields": []
        }
    }
]

def seed_templates(db: Session):
    for template_data in INITIAL_TEMPLATES:
        stmt = select(Template).where(Template.name == template_data["name"])
        existing = db.scalars(stmt).first()
        if not existing:
            new_template = Template(**template_data)
            db.add(new_template)
            logger.info(f"Seeded template: {template_data['name']}")
    db.commit()

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_templates(db)
        print("Templates seeded successfully!")
    finally:
        db.close()
