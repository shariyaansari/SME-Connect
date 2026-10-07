from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class ScheduleAdapter(BaseConnectorAdapter):
    slug = "schedule"
    name = "Schedule / Recurring Timer"
    category = "Productivity"
    description = "Trigger workflows automatically on an hourly, daily, or weekly recurring schedule."
    icon = "clock"
    auth_type = "none"

    config_fields = [
        {
            "key": "frequency",
            "label": "Frequency",
            "type": "select",
            "options": ["hourly", "daily", "weekly"],
            "required": True,
            "help_text": "How often the workflow should trigger",
        },
        {
            "key": "minute",
            "label": "Minute of Hour (0-59)",
            "type": "number",
            "required": False,
            "placeholder": "0",
            "help_text": "Minute within the hour to execute",
        },
        {
            "key": "hour",
            "label": "Hour of Day (0-23)",
            "type": "number",
            "required": False,
            "placeholder": "9",
            "help_text": "Hour of day (24h format) for daily/weekly schedules",
        },
        {
            "key": "day_of_week",
            "label": "Day of Week (0-6 or mon-sun)",
            "type": "text",
            "required": False,
            "placeholder": "0",
            "help_text": "Day of week for weekly schedules (0=Monday, 6=Sunday)",
        },
        {
            "key": "timezone",
            "label": "Timezone",
            "type": "text",
            "required": False,
            "placeholder": "UTC",
            "help_text": "Timezone name (e.g. UTC, America/New_York, Asia/Kolkata)",
        },
    ]

    credential_fields: list[dict[str, Any]] = []

    supported_triggers = [
        {
            "slug": "scheduled",
            "name": "Recurring Schedule",
            "description": "Fires automatically when the configured recurring time arrives.",
            "payload_schema": {
                "scheduled_time": {
                    "type": "string",
                    "label": "Scheduled Timestamp",
                    "description": "ISO 8601 timestamp of schedule trigger occurrence",
                },
                "frequency": {
                    "type": "string",
                    "label": "Frequency",
                    "description": "Recurrence frequency (hourly, daily, weekly)",
                },
                "timezone": {
                    "type": "string",
                    "label": "Timezone",
                    "description": "Configured timezone",
                },
                "slot": {
                    "type": "string",
                    "label": "Schedule Slot",
                    "description": "Deterministic slot identifier for deduplication",
                },
            },
        }
    ]

    supported_actions: list[dict[str, Any]] = []

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        return True, "Schedule connector ready"

    def read_trigger_data(
        self,
        trigger_slug: str,
        config: dict[str, Any],
        credentials: dict[str, Any],
        cursor: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Any | None]:
        # Schedule events are evaluated directly by the scheduler service
        return [], cursor

    def execute_action(
        self,
        action_slug: str,
        input_data: dict[str, Any],
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError("The Schedule connector does not provide action steps")
