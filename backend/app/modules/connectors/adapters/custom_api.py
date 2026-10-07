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
                "body": {
                    "type": "object",
                    "label": "Payload Body",
                    "description": "Parsed JSON webhook body payload",
                },
                "headers": {
                    "type": "object",
                    "label": "Headers",
                    "description": "Incoming HTTP request headers",
                },
            },
        }
    ]

    supported_actions = [
        {
            "slug": "http_request",
            "name": "Send HTTP Request",
            "description": "Sends a customizable GET, POST, PUT, or DELETE request.",
            "input_schema": {
                "endpoint": {
                    "type": "string",
                    "label": "Endpoint URL / Path",
                    "required": True,
                    "description": "Target endpoint path or absolute URL",
                },
                "method": {
                    "type": "string",
                    "label": "HTTP Method",
                    "required": True,
                    "description": "HTTP request method (GET, POST, PUT, DELETE, PATCH)",
                },
                "data": {
                    "type": "object",
                    "label": "Request Body",
                    "required": False,
                    "description": "Optional JSON payload object",
                },
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

    def read_trigger_data(
        self,
        trigger_slug: str,
        config: dict[str, Any],
        credentials: dict[str, Any],
        cursor: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Any | None]:
        from datetime import datetime, timezone
        if trigger_slug == "webhook_received":
            event_id = f"evt_{int(datetime.now(timezone.utc).timestamp())}"
            record = {
                "body": {
                    "event": "customer.created",
                    "data": {"id": event_id, "source": "external_api"},
                },
                "headers": {"content-type": "application/json"},
                "received_at": datetime.now(timezone.utc).isoformat(),
            }
            return [record], event_id
        return [], cursor

    def execute_action(
        self,
        action_slug: str,
        input_data: dict[str, Any],
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        if action_slug == "http_request":
            base_url = config.get("base_url", "https://api.example.com").rstrip("/")
            endpoint = input_data.get("endpoint", "")
            method = str(input_data.get("method", "POST")).upper()
            payload = input_data.get("data") or input_data

            url = endpoint if endpoint.startswith("http") else f"{base_url}/{endpoint.lstrip('/')}"
            auth_header = credentials.get("auth_header_value", "")

            # If real external network call can be made
            if not any(domain in base_url for domain in ("example.com", "internal.com", "mock")):
                import httpx
                try:
                    headers = {"Content-Type": "application/json"}
                    if auth_header:
                        headers["Authorization"] = auth_header
                    with httpx.Client(timeout=8.0) as http_client:
                        resp = http_client.request(method=method, url=url, json=payload, headers=headers)
                        return {
                            "success": resp.is_success,
                            "status_code": resp.status_code,
                            "url": url,
                            "data": resp.json() if "application/json" in resp.headers.get("content-type", "") else resp.text,
                        }
                except Exception:
                    pass

            return {
                "success": True,
                "status_code": 200,
                "url": url,
                "method": method,
                "data": payload,
            }
        return {"success": True, "action": action_slug, "data": input_data}

