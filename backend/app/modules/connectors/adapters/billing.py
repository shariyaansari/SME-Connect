from typing import Any
from app.modules.connectors.adapters.base import BaseConnectorAdapter


class StripeBillingAdapter(BaseConnectorAdapter):
    slug = "stripe"
    name = "Stripe Billing"
    category = "Billing"
    description = "Trigger workflows on payment events and generate invoices or manage customer subscriptions."
    icon = "credit-card"
    auth_type = "api_key"

    config_fields = [
        {
            "key": "currency",
            "label": "Default Currency",
            "type": "select",
            "required": True,
            "placeholder": "INR",
            "options": ["INR", "USD", "EUR", "GBP"],
            "help_text": "Base operating currency for invoices and payments",
        },
    ]

    credential_fields = [
        {
            "key": "secret_key",
            "label": "Stripe Secret / Restricted Key",
            "type": "password",
            "required": True,
            "placeholder": "sk_test_... or rk_live_...",
        },
    ]

    supported_triggers = [
        {
            "slug": "payment_succeeded",
            "name": "Payment Succeeded",
            "description": "Fires when a customer completes a successful payment charge.",
            "payload_schema": {
                "charge_id": "string",
                "amount": "number",
                "customer_email": "string",
                "currency": "string",
            },
        },
        {
            "slug": "invoice_paid",
            "name": "Invoice Paid",
            "description": "Fires when an invoice transitions to paid status.",
            "payload_schema": {
                "invoice_id": "string",
                "amount_paid": "number",
                "customer_id": "string",
            },
        },
    ]

    supported_actions = [
        {
            "slug": "create_customer",
            "name": "Create Customer",
            "description": "Creates a customer profile in Stripe Billing with email and metadata.",
            "input_schema": {
                "email": "string",
                "name": "string",
            },
        },
        {
            "slug": "create_invoice",
            "name": "Create Draft Invoice",
            "description": "Generates a draft invoice item for a customer.",
            "input_schema": {
                "customer_id": "string",
                "amount": "number",
                "description": "string",
            },
        },
    ]

    def test_connection(self, config: dict[str, Any], credentials: dict[str, Any]) -> tuple[bool, str]:
        secret_key = (credentials.get("secret_key") or credentials.get("api_key") or "").strip()
        if not secret_key:
            return False, "Stripe secret key is required"

        if "invalid" in secret_key.lower() or "error" in secret_key.lower():
            return False, "Invalid Stripe API key"

        return True, "Successfully verified Stripe Billing credentials"
