"""Stripe settlement adapter for XAP.

Uses Stripe Connect for multi-party settlements.
Test mode: uses sk_test_ keys, no real money moves.
Production mode: uses sk_live_ keys, real money.

Requires: pip install stripe
"""

from __future__ import annotations

from xap.adapters.base import SettlementAdapter
from xap.errors import XAPAdapterError


class StripeAdapter(SettlementAdapter):
    """Stripe Connect adapter for real payment settlements."""

    def __init__(self, api_key: str, webhook_secret: str | None = None) -> None:
        """Initialize the Stripe adapter.

        Args:
            api_key: Stripe secret key (sk_test_... or sk_live_...)
            webhook_secret: Stripe webhook signing secret (whsec_...)
        """
        self._validate_key(api_key)
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.is_test = api_key.startswith("sk_test_")

        # Agent-to-Stripe-account mapping
        self._account_map: dict[str, str] = {}

    def map_agent_to_stripe_account(self, agent_id: str, stripe_account_id: str) -> None:
        """Map an XAP agent_id to a Stripe Connect account."""
        self._account_map[agent_id] = stripe_account_id

    async def lock_funds(self, settlement: dict) -> dict:
        """Create a Stripe PaymentIntent with manual capture.

        Authorizes the amount without capturing it (places a hold).
        """
        stripe = _require_stripe()
        stripe.api_key = self.api_key

        amount = settlement["total_amount_minor_units"]
        currency = settlement["currency"].lower()

        try:
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                capture_method="manual",
                metadata={
                    "settlement_id": settlement["settlement_id"],
                    "xap_version": settlement.get("xap_version", "0.2.0"),
                    "payer_agent": settlement.get("payer_agent", ""),
                },
                payment_method="pm_card_visa" if self.is_test else None,
                confirm=True if self.is_test else False,
            )
        except stripe.error.StripeError as e:
            raise XAPAdapterError(f"Stripe lock_funds failed: {e}") from e

        return {
            "status": "locked",
            "payment_intent_id": intent.id,
            "amount_authorized": intent.amount,
            "currency": intent.currency,
            "adapter": "stripe",
            "adapter_trace": {
                "payment_intent_id": intent.id,
                "status": intent.status,
                "created": intent.created,
            },
        }

    async def release_funds(self, settlement: dict, payouts: list[dict]) -> dict:
        """Capture the PaymentIntent and distribute via Stripe Connect transfers.

        For single payee: capture goes directly.
        For split: capture to platform, then transfer to each connected account.
        """
        stripe = _require_stripe()
        stripe.api_key = self.api_key

        lock_ref = settlement.get("lock_reference", {})
        payment_intent_id = lock_ref.get("payment_intent_id")

        if not payment_intent_id:
            raise XAPAdapterError("No payment_intent_id in lock reference")

        try:
            intent = stripe.PaymentIntent.capture(payment_intent_id)
        except stripe.error.StripeError as e:
            raise XAPAdapterError(f"Stripe capture failed: {e}") from e

        transfers = []
        for payout in payouts:
            agent_id = payout["agent_id"]
            amount = payout["amount_minor_units"]

            stripe_account = self._account_map.get(agent_id)
            if not stripe_account:
                if self.is_test:
                    transfers.append({
                        "agent_id": agent_id,
                        "amount": amount,
                        "status": "skipped_test_mode",
                        "reason": "no Stripe Connect account mapped",
                    })
                    continue
                else:
                    raise XAPAdapterError(
                        f"No Stripe Connect account mapped for agent {agent_id}"
                    )

            try:
                transfer = stripe.Transfer.create(
                    amount=amount,
                    currency=settlement["currency"].lower(),
                    destination=stripe_account,
                    source_transaction=intent.latest_charge,
                    metadata={
                        "settlement_id": settlement["settlement_id"],
                        "agent_id": agent_id,
                    },
                )
                transfers.append({
                    "agent_id": agent_id,
                    "amount": amount,
                    "transfer_id": transfer.id,
                    "status": "completed",
                })
            except stripe.error.StripeError as e:
                transfers.append({
                    "agent_id": agent_id,
                    "amount": amount,
                    "status": "failed",
                    "error": str(e),
                })

        return {
            "status": "settled",
            "payment_intent_id": payment_intent_id,
            "charge_id": intent.latest_charge,
            "transfers": transfers,
            "adapter": "stripe",
            "adapter_trace": {
                "payment_intent_id": payment_intent_id,
                "charge_id": intent.latest_charge,
                "capture_status": intent.status,
                "transfer_count": len(transfers),
            },
        }

    async def refund(self, settlement: dict, amount: int) -> dict:
        """Cancel uncaptured PaymentIntent or refund captured amount."""
        stripe = _require_stripe()
        stripe.api_key = self.api_key

        lock_ref = settlement.get("lock_reference", {})
        payment_intent_id = lock_ref.get("payment_intent_id")

        if not payment_intent_id:
            raise XAPAdapterError("No payment_intent_id in lock reference")

        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status == "requires_capture":
                stripe.PaymentIntent.cancel(payment_intent_id)
                return {
                    "status": "refunded",
                    "method": "cancel_uncaptured",
                    "amount": amount,
                    "payment_intent_id": payment_intent_id,
                    "adapter": "stripe",
                }
            else:
                refund_obj = stripe.Refund.create(
                    payment_intent=payment_intent_id,
                    amount=amount,
                )
                return {
                    "status": "refunded",
                    "method": "refund_captured",
                    "refund_id": refund_obj.id,
                    "amount": refund_obj.amount,
                    "payment_intent_id": payment_intent_id,
                    "adapter": "stripe",
                }
        except stripe.error.StripeError as e:
            raise XAPAdapterError(f"Stripe refund failed: {e}") from e

    def adapter_type(self) -> str:
        return "stripe"

    def default_finality(self) -> str:
        return "within_reversal_window"

    def _validate_key(self, key: str) -> None:
        if not key.startswith(("sk_test_", "sk_live_")):
            raise ValueError("Stripe API key must start with sk_test_ or sk_live_")


def _require_stripe():
    """Lazy import for stripe module."""
    try:
        import stripe
        return stripe
    except ImportError:
        raise ImportError(
            "stripe is required for the Stripe adapter. "
            "Install it with: pip install stripe"
        )
