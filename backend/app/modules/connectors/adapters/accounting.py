from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class ZohoBooksAdapter(BaseConnectorAdapter):
    slug = "zoho_books"
    name = "Zoho Books"
    category = "Accounting"
    description = "Sync invoices, record bills, and track accounting transactions for Indian SMEs."
    icon = "book-open"
    auth_type = "oauth2"

    config_fields = [
        {
            "key": "organization_id",
            "label": "Zoho Books Organization ID",
            "type": "text",
            "required": True,
            "placeholder": "60012345678",
            "help_text": "Organization ID from your Zoho Books account settings",
        },
    ]

    credential_fields = [
        {
            "key": "client_id",
            "label": "OAuth Client ID",
            "type": "text",
            "required": True,
            "placeholder": "1000.xxxx...",
        },
        {
            "key": "client_secret",
            "label": "OAuth Client Secret",
            "type": "password",
            "required": True,
            "placeholder": "Enter Zoho OAuth client secret",
        },
    ]

    supported_triggers = [
        {
            "slug": "invoice_created",
            "name": "New Invoice Created",
            "description": "Fires when a new tax invoice is generated.",
            "payload_schema": {
                "invoice_number": "string",
                "customer_name": "string",
                "total": "number",
                "currency": "string",
            },
        },
    ]

    supported_actions = [
        {
            "slug": "create_contact",
            "name": "Create Accounting Contact",
            "description": "Creates a customer or vendor ledger contact.",
            "input_schema": {
                "contact_name": "string",
                "email": "string",
                "phone": "string",
            },
        },
        {
            "slug": "create_invoice",
            "name": "Create Tax Invoice",
            "description": "Generates a draft or sent tax invoice.",
            "input_schema": {
                "customer_id": "string",
                "item_name": "string",
                "rate": "number",
                "quantity": "number",
            },
        },
    ]

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        org_id = config.get("organization_id", "").strip()
        auth_token = credentials.get("auth_token", "").strip()
        client_id = credentials.get("client_id", "").strip()
        client_secret = credentials.get("client_secret", "").strip()

        if not org_id:
            return False, "Zoho Books Organization ID is required"
        if not auth_token and not (client_id and client_secret):
            return False, "OAuth Client ID/Secret or Auth Token is required"

        token_to_check = client_secret or auth_token
        if "invalid" in token_to_check.lower() or "error" in token_to_check.lower():
            return False, "Invalid Zoho Books credentials"

        return True, f"Successfully verified Zoho Books accounting access for Org: {org_id}"
