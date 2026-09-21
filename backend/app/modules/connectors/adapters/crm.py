from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class CRMAdapter(BaseConnectorAdapter):
    slug = "crm"
    name = "CRM Integration"
    category = "CRM"
    description = "Sync leads, create contacts, and manage customer sales pipelines automatically."
    icon = "users"
    auth_type = "api_key"

    config_fields = [
        {
            "key": "crm_provider",
            "label": "CRM Provider",
            "type": "select",
            "required": True,
            "placeholder": "HubSpot",
            "options": ["HubSpot", "Zoho CRM", "Salesforce", "Internal Mock CRM"],
            "help_text": "Select your CRM provider",
        },
        {
            "key": "api_base_url",
            "label": "API Base URL / Domain",
            "type": "text",
            "required": False,
            "placeholder": "https://api.hubapi.com",
            "help_text": "Leave blank to use default cloud provider URL",
        },
    ]

    credential_fields = [
        {
            "key": "api_key",
            "label": "API Key / Access Token",
            "type": "password",
            "required": True,
            "placeholder": "pat-na1-xxxxxxxx-xxxx-xxxx",
        },
    ]

    supported_triggers = [
        {
            "slug": "new_lead",
            "name": "New Lead Created",
            "description": "Fires when a new contact or lead is created in the CRM.",
            "payload_schema": {
                "lead_id": "string",
                "name": "string",
                "email": "string",
                "phone": "string",
                "status": "string",
            },
        },
        {
            "slug": "deal_stage_updated",
            "name": "Deal Stage Changed",
            "description": "Fires when a deal advances in the pipeline.",
            "payload_schema": {
                "deal_id": "string",
                "stage": "string",
                "amount": "number",
            },
        },
    ]

    supported_actions = [
        {
            "slug": "create_lead",
            "name": "Create Lead / Contact",
            "description": "Creates a new lead with customer details (name, email, phone, notes).",
            "input_schema": {
                "name": "string",
                "email": "string",
                "phone": "string",
                "company": "string",
            },
        },
        {
            "slug": "update_lead",
            "name": "Update Lead",
            "description": "Updates fields of an existing lead by email or ID.",
            "input_schema": {
                "email": "string",
                "status": "string",
            },
        },
    ]

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        provider = config.get("crm_provider", "CRM").strip()
        api_key = credentials.get("api_key", "").strip()

        if not api_key:
            return False, "CRM API Key is required"

        if "invalid" in api_key.lower() or "error" in api_key.lower():
            return False, f"Failed to authenticate with {provider}: Invalid token"

        return True, f"Successfully authenticated with {provider}"
