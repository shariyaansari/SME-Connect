from app.modules.connectors.adapters.accounting import ZohoBooksAdapter
from app.modules.connectors.adapters.base import BaseConnectorAdapter
from app.modules.connectors.adapters.billing import StripeBillingAdapter
from app.modules.connectors.adapters.crm import CRMAdapter
from app.modules.connectors.adapters.custom_api import CustomAPIAdapter
from app.modules.connectors.adapters.google_sheets import GoogleSheetsAdapter
from app.modules.connectors.adapters.whatsapp import WhatsAppAdapter

ADAPTERS: dict[str, BaseConnectorAdapter] = {
    GoogleSheetsAdapter.slug: GoogleSheetsAdapter(),
    CRMAdapter.slug: CRMAdapter(),
    StripeBillingAdapter.slug: StripeBillingAdapter(),
    ZohoBooksAdapter.slug: ZohoBooksAdapter(),
    CustomAPIAdapter.slug: CustomAPIAdapter(),
    WhatsAppAdapter.slug: WhatsAppAdapter(),
}


def get_catalog() -> list[dict[str, Any]]:
    return [adapter.to_catalog_dict() for adapter in ADAPTERS.values()]


def get_adapter(slug: str) -> BaseConnectorAdapter | None:
    return ADAPTERS.get(slug)


def is_valid_connector(slug: str) -> bool:
    return slug in ADAPTERS
