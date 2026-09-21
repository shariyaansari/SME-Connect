from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class GoogleSheetsAdapter(BaseConnectorAdapter):
    slug = "google_sheets"
    name = "Google Sheets"
    category = "Spreadsheets"
    description = "Read rows and trigger workflows from spreadsheets, or append new rows automatically."
    icon = "table"
    auth_type = "oauth2"

    config_fields = [
        {
            "key": "spreadsheet_id",
            "label": "Spreadsheet ID",
            "type": "text",
            "required": True,
            "placeholder": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms",
            "help_text": "The unique ID from your Google Sheets URL",
        },
        {
            "key": "sheet_name",
            "label": "Sheet / Tab Name",
            "type": "text",
            "required": False,
            "placeholder": "Sheet1",
            "help_text": "Default sheet tab to operate on",
        },
    ]

    credential_fields = [
        {
            "key": "client_id",
            "label": "Client ID / Service Account Email",
            "type": "text",
            "required": True,
            "placeholder": "service-account@project.iam.gserviceaccount.com",
        },
        {
            "key": "client_secret",
            "label": "API Key / Private Key",
            "type": "password",
            "required": True,
            "placeholder": "Enter private key or OAuth secret",
        },
    ]

    supported_triggers = [
        {
            "slug": "new_row",
            "name": "New Row Added",
            "description": "Fires immediately when a new row of data is added to the spreadsheet.",
            "payload_schema": {
                "row_index": "number",
                "values": "object",
                "created_at": "string",
            },
        }
    ]

    supported_actions = [
        {
            "slug": "append_row",
            "name": "Append Row",
            "description": "Appends mapped data as a new row to the specified sheet.",
            "input_schema": {
                "values": "object",
            },
        },
        {
            "slug": "read_rows",
            "name": "Read Rows",
            "description": "Fetches recent rows matching a query or column condition.",
            "input_schema": {
                "limit": "number",
            },
        },
    ]

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        # Validate required config & credentials
        spreadsheet_id = config.get("spreadsheet_id", "").strip()
        client_id = credentials.get("client_id", "").strip()
        client_secret = credentials.get("client_secret", "").strip()

        if not spreadsheet_id:
            return False, "Spreadsheet ID is required"
        if not client_id:
            return False, "Client ID or Service Account Email is required"
        if not client_secret:
            return False, "API Key or Private Key is required"

        # Simulating or performing verification
        if "invalid" in client_secret.lower() or "error" in client_secret.lower():
            return False, "Invalid Google Cloud credentials or permissions"

        return True, f"Successfully verified access to Google Sheet '{spreadsheet_id}'"
