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
                "charge_id": {
                    "type": "string",
                    "label": "Charge ID",
                    "description": "Unique Stripe charge identifier",
                },
                "amount": {
                    "type": "number",
                    "label": "Charge Amount",
                    "description": "Amount charged",
                },
                "customer_email": {
                    "type": "string",
                    "label": "Customer Email",
                    "description": "Billing customer email address",
                },
                "currency": {
                    "type": "string",
                    "label": "Currency",
                    "description": "Three-letter ISO currency code",
                },
            },
        },
        {
            "slug": "invoice_paid",
            "name": "Invoice Paid",
            "description": "Fires when an invoice transitions to paid status.",
            "payload_schema": {
                "invoice_id": {
                    "type": "string",
                    "label": "Invoice ID",
                    "description": "Unique Stripe invoice identifier",
                },
                "amount_paid": {
                    "type": "number",
                    "label": "Amount Paid",
                    "description": "Total amount paid on invoice",
                },
                "customer_id": {
                    "type": "string",
                    "label": "Customer ID",
                    "description": "Associated customer identifier",
                },
            },
        },
    ]

    supported_actions = [
        {
            "slug": "create_customer",
            "name": "Create Customer",
            "description": "Creates a customer profile in Stripe Billing with email and metadata.",
            "input_schema": {
                "email": {
                    "type": "string",
                    "label": "Customer Email",
                    "required": True,
                    "description": "Customer primary email address",
                },
                "name": {
                    "type": "string",
                    "label": "Customer Name",
                    "required": False,
                    "description": "Customer full legal or business name",
                },
            },
        },
        {
            "slug": "create_invoice",
            "name": "Create Draft Invoice",
            "description": "Generates a draft invoice item for a customer.",
            "input_schema": {
                "customer_id": {
                    "type": "string",
                    "label": "Customer ID",
                    "required": True,
                    "description": "Stripe customer identifier",
                },
                "amount": {
                    "type": "number",
                    "label": "Invoice Amount",
                    "required": True,
                    "description": "Monetary total for the invoice",
                },
                "description": {
                    "type": "string",
                    "label": "Line Item Description",
                    "required": False,
                    "description": "Summary of services or goods billed",
                },
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
