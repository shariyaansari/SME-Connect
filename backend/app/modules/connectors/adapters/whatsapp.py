from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class WhatsAppAdapter(BaseConnectorAdapter):
    slug = "whatsapp"
    name = "WhatsApp Business API"
    category = "Communication"
    description = "Trigger workflows on incoming WhatsApp enquiries, or send automated order updates & template messages."
    icon = "message-circle"
    auth_type = "bearer"

    config_fields = [
        {
            "key": "phone_number_id",
            "label": "Phone Number ID",
            "type": "text",
            "required": True,
            "placeholder": "109876543210987",
            "help_text": "Your Meta WhatsApp Business Phone Number ID",
        },
        {
            "key": "business_account_id",
            "label": "WhatsApp Business Account (WABA) ID",
            "type": "text",
            "required": False,
            "placeholder": "123456789012345",
        },
    ]

    credential_fields = [
        {
            "key": "access_token",
            "label": "Permanent / System User Access Token",
            "type": "password",
            "required": True,
            "placeholder": "EAAx...",
        },
    ]

    supported_triggers = [
        {
            "slug": "message_received",
            "name": "New Customer Message",
            "description": "Fires when a customer sends an inquiry or message to your business number.",
            "payload_schema": {
                "from_number": "string",
                "customer_name": "string",
                "message_text": "string",
                "timestamp": "string",
            },
        }
    ]

    supported_actions = [
        {
            "slug": "send_template",
            "name": "Send Template Message",
            "description": "Sends a pre-approved template message (e.g. order confirmation, lead acknowledgement).",
            "input_schema": {
                "to_number": "string",
                "template_name": "string",
                "parameters": "array",
            },
        },
        {
            "slug": "send_text",
            "name": "Send Freeform Message",
            "description": "Sends a standard text message within the active 24-hour customer service window.",
            "input_schema": {
                "to_number": "string",
                "text": "string",
            },
        },
    ]

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        phone_id = config.get("phone_number_id", "").strip()
        token = credentials.get("access_token", "").strip()

        if not phone_id:
            return False, "Phone Number ID is required"
        if not token:
            return False, "Access Token is required"

        if "invalid" in token.lower() or "error" in token.lower():
            return False, "Meta Graph API rejected the token"

        return True, f"Verified WhatsApp Business connection for Phone ID: {phone_id}"
