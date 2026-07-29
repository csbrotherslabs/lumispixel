"""Stable boundaries for payment and physical fulfillment integrations."""
from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrationResult:
    accepted: bool
    reference: str = ""
    message: str = "Integration is not configured."


class PaymentGateway:
    """Interface reserved for a future Stripe adapter."""
    def create_payment(self, order) -> IntegrationResult:
        return IntegrationResult(False)


class FulfillmentProvider:
    """Interface reserved for a future print-lab adapter."""
    def submit_order(self, order) -> IntegrationResult:
        return IntegrationResult(False)
