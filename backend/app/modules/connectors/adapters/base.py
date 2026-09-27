from abc import ABC, abstractmethod
from typing import Any


class BaseConnectorAdapter(ABC):
    slug: str
    name: str
    category: str
    description: str
    icon: str
    auth_type: str = "api_key"
    config_fields: list[dict[str, Any]] = []
    credential_fields: list[dict[str, Any]] = []
    supported_triggers: list[dict[str, Any]] = []
    supported_actions: list[dict[str, Any]] = []

    def to_catalog_dict(self) -> dict[str, Any]:
        return {
            "slug": self.slug,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "icon": self.icon,
            "auth_type": self.auth_type,
            "config_fields": self.config_fields,
            "credential_fields": self.credential_fields,
            "supported_triggers": self.supported_triggers,
            "supported_actions": self.supported_actions,
        }

    @abstractmethod
    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        """
        Validate credentials and verify health of the external service.
        Returns:
            (True, "Connection successful") or (False, "Failure explanation")
        """
        raise NotImplementedError

    def read_trigger_data(
        self,
        trigger_slug: str,
        config: dict[str, Any],
        credentials: dict[str, Any],
        cursor: Any | None = None,
    ) -> tuple[list[dict[str, Any]], Any | None]:
        """
        Poll or fetch events for a trigger.
        Returns:
            (records, new_cursor)
        """
        return [], cursor

    def execute_action(
        self,
        action_slug: str,
        input_data: dict[str, Any],
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute an action with input data.
        Returns:
            Result dict with execution outcome/response payload.
        """
        return {"status": "success", "action": action_slug, "data": input_data}

