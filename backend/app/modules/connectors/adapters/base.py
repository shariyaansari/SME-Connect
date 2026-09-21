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
