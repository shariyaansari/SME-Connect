from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class CustomAPIAdapter(BaseConnectorAdapter):
    slug = "custom_api"
    name = "Custom REST API / Webhook"
    category = "Developer Tools"
    description = "Connect to any custom internal software, cloud service, or webhook via REST API."
    icon = "globe"
    auth_type = "bearer"

    config_fields = [
        {
            "key": "base_url",
            "label": "Base URL / Endpoint",
            "type": "url",
            "required": True,
            "placeholder": "https://api.example.com/v1",
            "help_text": "Root URL or target webhook destination",
        },
        {
            "key": "headers",
            "label": "Custom Headers (JSON or comma separated)",
            "type": "text",
            "required": False,
            "placeholder": '{"Content-Type": "application/json"}',
            "help_text": "Default headers to include with requests",
        },
    ]

    credential_fields = [
        {
            "key": "auth_header_value",
            "label": "Bearer Token / Authorization Header",
            "type": "password",
            "required": False,
            "placeholder": "Bearer your-secret-token",
        },
    ]

    supported_triggers = [
        {
            "slug": "webhook_received",
            "name": "Incoming Webhook",
            "description": "Fires whenever an external system posts a payload to this endpoint.",
            "payload_schema": {
                "body": "object",
                "headers": "object",
            },
        }
    ]

    supported_actions = [
        {
            "slug": "http_request",
            "name": "Send HTTP Request",
            "description": "Sends a customizable GET, POST, PUT, or DELETE request.",
            "input_schema": {
                "endpoint": "string",
                "method": "string",
                "data": "object",
            },
        }
    ]

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        base_url = config.get("base_url", "").strip()
        if not base_url:
            return False, "Base URL is required"

        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            return False, "Base URL must start with http:// or https://"

        return True, f"Configured custom API endpoint: {base_url}"
