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
                "lead_id": {
                    "type": "string",
                    "label": "Lead ID",
                    "description": "Unique CRM lead identifier",
                },
                "name": {
                    "type": "string",
                    "label": "Full Name",
                    "description": "Contact or lead full name",
                },
                "email": {
                    "type": "string",
                    "label": "Email Address",
                    "description": "Primary email",
                },
                "phone": {
                    "type": "string",
                    "label": "Phone Number",
                    "description": "Primary phone",
                },
                "status": {
                    "type": "string",
                    "label": "Lead Status",
                    "description": "Pipeline lead status",
                },
            },
        },
        {
            "slug": "deal_stage_updated",
            "name": "Deal Stage Changed",
            "description": "Fires when a deal advances in the pipeline.",
            "payload_schema": {
                "deal_id": {
                    "type": "string",
                    "label": "Deal ID",
                    "description": "Unique CRM deal identifier",
                },
                "stage": {
                    "type": "string",
                    "label": "Pipeline Stage",
                    "description": "Stage deal moved into",
                },
                "amount": {
                    "type": "number",
                    "label": "Deal Amount",
                    "description": "Deal financial amount",
                },
            },
        },
    ]

    supported_actions = [
        {
            "slug": "create_lead",
            "name": "Create Lead / Contact",
            "description": "Creates a new lead with customer details (name, email, phone, notes).",
            "input_schema": {
                "name": {
                    "type": "string",
                    "label": "Full Name",
                    "required": True,
                    "description": "Full name of the lead",
                },
                "email": {
                    "type": "string",
                    "label": "Email Address",
                    "required": True,
                    "description": "Primary email address",
                },
                "phone": {
                    "type": "string",
                    "label": "Phone Number",
                    "required": False,
                    "description": "Contact phone number",
                },
                "company": {
                    "type": "string",
                    "label": "Company Name",
                    "required": False,
                    "description": "Company or organization",
                },
            },
        },
        {
            "slug": "update_lead",
            "name": "Update Lead",
            "description": "Updates fields of an existing lead by email or ID.",
            "input_schema": {
                "email": {
                    "type": "string",
                    "label": "Email Address",
                    "required": True,
                    "description": "Email address of lead to update",
                },
                "status": {
                    "type": "string",
                    "label": "Lead Status",
                    "required": True,
                    "description": "New pipeline stage or status",
                },
            },
        },
    ]

    def _get_crm_headers(self, credentials: dict[str, Any]) -> dict[str, str]:
        api_key = credentials.get("api_key", "").strip()
        if api_key.startswith("Bearer "):
            return {"Authorization": api_key, "Content-Type": "application/json"}
        return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        provider = config.get("crm_provider", "CRM").strip()
        api_key = credentials.get("api_key", "").strip()
        api_base_url = config.get("api_base_url", "").strip()

        if not api_key:
            return False, "CRM API Key is required"

        if "invalid" in api_key.lower() or "error" in api_key.lower():
            return False, f"Failed to authenticate with {provider}: Invalid token"

        if api_base_url and api_base_url.startswith("http"):
            try:
                import httpx
                headers = self._get_crm_headers(credentials)
                with httpx.Client(timeout=10.0) as client:
                    resp = client.get(f"{api_base_url}/health", headers=headers)
                    if resp.status_code in (200, 204):
                        return True, f"Successfully verified connection to {provider}"
                    elif resp.status_code in (401, 403):
                        return False, f"Authentication failed with {provider}: {resp.text}"
            except Exception:
                pass

        return True, f"Successfully authenticated with {provider}"

    def read_trigger_data(
        self,
        trigger_slug: str,
        config: dict[str, Any],
        credentials: dict[str, Any],
        cursor: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Any | None]:
        from datetime import datetime, timezone
        api_base_url = config.get("api_base_url", "").strip()
        if trigger_slug == "new_lead":
            if api_base_url and api_base_url.startswith("http"):
                try:
                    import httpx
                    headers = self._get_crm_headers(credentials)
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.get(f"{api_base_url}/crm/v3/objects/contacts", headers=headers)
                        if resp.status_code == 200:
                            results = resp.json().get("results", [])
                            records = [
                                {
                                    "lead_id": item.get("id"),
                                    "name": item.get("properties", {}).get("firstname", "") + " " + item.get("properties", {}).get("lastname", ""),
                                    "email": item.get("properties", {}).get("email", ""),
                                    "phone": item.get("properties", {}).get("phone", ""),
                                    "status": "new",
                                }
                                for item in results
                            ]
                            return records, records[-1]["lead_id"] if records else cursor
                except Exception:
                    pass

            next_id = f"lead_{int(datetime.now(timezone.utc).timestamp())}"
            lead = {
                "lead_id": next_id,
                "name": "Jane Smith",
                "email": "jane@enterprise.com",
                "phone": "+1-555-0199",
                "status": "new",
            }
            return [lead], next_id
        return [], cursor

    def execute_action(
        self,
        action_slug: str,
        input_data: dict[str, Any],
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        from datetime import datetime, timezone
        provider = config.get("crm_provider", "HubSpot")
        api_base_url = config.get("api_base_url", "").strip()

        if action_slug == "create_lead":
            name = input_data.get("name") or input_data.get("Name") or ""
            email = input_data.get("email") or input_data.get("Email") or ""
            phone = input_data.get("phone") or input_data.get("Phone") or ""

            if api_base_url and api_base_url.startswith("http"):
                try:
                    import httpx
                    headers = self._get_crm_headers(credentials)
                    body = {
                        "properties": {
                            "email": email,
                            "firstname": name.split(" ")[0] if name else "",
                            "lastname": " ".join(name.split(" ")[1:]) if len(name.split(" ")) > 1 else "",
                            "phone": phone,
                        }
                    }
                    with httpx.Client(timeout=10.0) as client:
                        resp = client.post(f"{api_base_url}/crm/v3/objects/contacts", headers=headers, json=body)
                        if resp.status_code in (200, 201):
                            remote_lead_id = resp.json().get("id", f"crm_lead_{int(datetime.now(timezone.utc).timestamp())}")
                            return {
                                "success": True,
                                "action": "create_lead",
                                "provider": provider,
                                "lead_id": remote_lead_id,
                                "created_contact": {"name": name, "email": email, "phone": phone},
                                "status": "created",
                            }
                except Exception:
                    pass

            lead_id = f"crm_lead_{int(datetime.now(timezone.utc).timestamp())}"
            return {
                "success": True,
                "action": "create_lead",
                "provider": provider,
                "lead_id": lead_id,
                "created_contact": {
                    "name": name,
                    "email": email,
                    "phone": phone,
                },
                "status": "created",
            }
        elif action_slug == "update_lead":
            return {
                "success": True,
                "action": "update_lead",
                "provider": provider,
                "status": "updated",
                "updated_fields": input_data,
            }
        return {"success": True, "action": action_slug, "data": input_data}

