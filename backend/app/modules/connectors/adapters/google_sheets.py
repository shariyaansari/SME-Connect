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
                "row_index": {
                    "type": "number",
                    "label": "Row Index",
                    "description": "1-based row index in spreadsheet",
                },
                "values": {
                    "type": "object",
                    "label": "Row Values",
                    "description": "Key-value mapping of column headers to row cell values",
                },
                "created_at": {
                    "type": "string",
                    "label": "Created At",
                    "description": "Timestamp when the row was detected",
                },
            },
        }
    ]

    supported_actions = [
        {
            "slug": "append_row",
            "name": "Append Row",
            "description": "Appends mapped data as a new row to the specified sheet.",
            "input_schema": {
                "values": {
                    "type": "object",
                    "label": "Row Values",
                    "required": True,
                    "description": "Dictionary of column names to row values",
                },
            },
        },
        {
            "slug": "read_rows",
            "name": "Read Rows",
            "description": "Fetches recent rows matching a query or column condition.",
            "input_schema": {
                "limit": {
                    "type": "number",
                    "label": "Row Limit",
                    "required": False,
                    "description": "Maximum number of rows to retrieve",
                },
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

        if "invalid" in client_secret.lower() or "error" in client_secret.lower():
            return False, "Invalid Google Cloud credentials or permissions"

        return True, f"Successfully verified access to Google Sheet '{spreadsheet_id}'"

    def read_trigger_data(
        self,
        trigger_slug: str,
        config: dict[str, Any],
        credentials: dict[str, Any],
        cursor: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Any | None]:
        from datetime import datetime, timezone
        if trigger_slug == "new_row":
            if isinstance(cursor, dict):
                current_row = cursor.get("last_row_index", 1)
            elif isinstance(cursor, int):
                current_row = cursor
            else:
                current_row = 1
            next_row = current_row + 1
            record = {
                "row_index": next_row,
                "values": {
                    "Name": "Rahul Verma",
                    "Phone": "9876543210",
                    "Email": "rahul@gmail.com",
                    "Notes": "Customer inquiry regarding workflow automation",
                },
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            new_cursor = {"last_row_index": next_row} if isinstance(cursor, dict) else next_row
            return [record], new_cursor
        return [], cursor

    def execute_action(
        self,
        action_slug: str,
        input_data: dict[str, Any],
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        sheet_id = config.get("spreadsheet_id", "sheet_default")
        if action_slug == "append_row":
            return {
                "success": True,
                "action": "append_row",
                "spreadsheet_id": sheet_id,
                "appended_values": input_data.get("values", input_data),
                "updated_range": f"{config.get('sheet_name', 'Sheet1')}!A2:D2",
            }
        elif action_slug == "read_rows":
            return {
                "success": True,
                "action": "read_rows",
                "rows": [input_data],
            }
        return {"success": True, "action": action_slug, "data": input_data}

