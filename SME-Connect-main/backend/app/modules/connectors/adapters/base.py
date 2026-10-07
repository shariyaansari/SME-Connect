from abc import ABC, abstractmethod
from typing import Any


class ConnectorExecutionError(Exception):
    """
    Standard structured exception for connector execution failures.
    Preserves error category and retryable semantics without leaking credentials.
    """
    def __init__(
        self,
        message: str,
        category: str = "connector_error",
        retryable: bool = True,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.retryable = retryable
        self.details = details or {}


class BaseConnectorAdapter(ABC):
    slug: str
    name: str
    category: str
    description: str
    icon: str
    auth_type: str = "api_key"
    config_fields: list[dict[str, Any]]
    credential_fields: list[dict[str, Any]]
    supported_triggers: list[dict[str, Any]]
    supported_actions: list[dict[str, Any]]

    def to_catalog_dict(self) -> dict[str, Any]:
        return {
            "slug": getattr(self, "slug", ""),
            "name": getattr(self, "name", ""),
            "category": getattr(self, "category", ""),
            "description": getattr(self, "description", ""),
            "icon": getattr(self, "icon", ""),
            "auth_type": getattr(self, "auth_type", "api_key"),
            "config_fields": getattr(self, "config_fields", []),
            "credential_fields": getattr(self, "credential_fields", []),
            "supported_triggers": getattr(self, "supported_triggers", []),
            "supported_actions": getattr(self, "supported_actions", []),
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
        Concrete adapters should override this for each supported trigger.
        """
        raise NotImplementedError(
            f"Trigger '{trigger_slug}' is not implemented by connector '{getattr(self, 'slug', 'unknown')}'"
        )

    def execute_action(
        self,
        action_slug: str,
        input_data: dict[str, Any],
        config: dict[str, Any],
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute an action with input data.
        Concrete adapters should override this for each supported action.
        """
        raise NotImplementedError(
            f"Action '{action_slug}' is not implemented by connector '{getattr(self, 'slug', 'unknown')}'"
        )
