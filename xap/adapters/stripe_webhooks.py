"""Stripe webhook handler for XAP.

Maps Stripe webhook events to XAP state transitions.
Used in production to handle async payment confirmations,
disputes, and refund notifications.

Requires: pip install stripe
"""

from __future__ import annotations


class StripeWebhookHandler:
    """Handle Stripe webhook events and map them to XAP state transitions."""

    def __init__(self, webhook_secret: str) -> None:
        """Initialize with Stripe webhook signing secret.

        Args:
            webhook_secret: Stripe webhook signing secret (whsec_...)
        """
        self.webhook_secret = webhook_secret

    def verify_and_parse(self, payload: bytes, signature: str) -> dict:
        """Verify webhook signature and parse the event.

        Args:
            payload: Raw request body bytes
            signature: Stripe-Signature header value

        Returns:
            Parsed Stripe event dict
        """
        try:
            import stripe
        except ImportError:
            raise ImportError(
                "stripe is required for webhook handling. "
                "Install it with: pip install stripe"
            )

        event = stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        return event

    def handle_event(self, event: dict) -> dict:
        """Map a Stripe event to an XAP action.

        Args:
            event: Parsed Stripe event (from verify_and_parse or test input)

        Returns:
            Dict with 'action' key indicating what XAP should do:
            - confirm_lock: Payment authorized successfully
            - lock_failed: Payment authorization failed
            - initiate_dispute: Chargeback/dispute opened
            - confirm_refund: Refund completed
            - ignore: Event not relevant to XAP
        """
        event_type = event["type"]

        if event_type == "payment_intent.succeeded":
            return {"action": "confirm_lock", "data": event["data"]["object"]}

        elif event_type == "payment_intent.payment_failed":
            return {"action": "lock_failed", "data": event["data"]["object"]}

        elif event_type == "charge.dispute.created":
            return {"action": "initiate_dispute", "data": event["data"]["object"]}

        elif event_type == "charge.refunded":
            return {"action": "confirm_refund", "data": event["data"]["object"]}

        elif event_type == "transfer.created":
            return {"action": "confirm_transfer", "data": event["data"]["object"]}

        elif event_type == "transfer.failed":
            return {"action": "transfer_failed", "data": event["data"]["object"]}

        else:
            return {"action": "ignore", "event_type": event_type}
