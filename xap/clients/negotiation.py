"""NegotiationClient — manage negotiation flows between agents."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xap.builders.negotiation import NegotiationContractBuilder
from xap.types import AgentId, CanonicalTimestamp

if TYPE_CHECKING:
    from xap.client import XAPClient


class NegotiationClient:
    """Manage negotiation flows between agents."""

    def __init__(self, xap_client: XAPClient) -> None:
        self._client = xap_client

    def create_offer(
        self,
        responder: AgentId,
        capability: str,
        amount_minor_units: int,
        currency: str = "USD",
        conditions: list[dict] | None = None,
        sla: dict | None = None,
        expires_in_seconds: int = 3600,
    ) -> dict:
        """Create a new negotiation offer.

        Returns a signed NegotiationContract in OFFER state.
        """
        task = {"type": capability}
        pricing = {
            "amount_minor_units": amount_minor_units,
            "currency": currency,
            "model": "fixed",
            "per": "request",
        }
        sla = sla or {"max_latency_ms": 5000}

        builder = NegotiationContractBuilder(self._client.signer)
        contract = (
            builder
            .new_offer(
                proposer=self._client.agent_id,
                responder=responder,
                task=task,
                pricing=pricing,
                sla=sla,
                expires_in_minutes=max(1, expires_in_seconds // 60),
            )
            .build()
        )
        return contract

    def counter_offer(
        self,
        original: dict,
        new_amount: int | None = None,
        new_conditions: list[dict] | None = None,
        new_sla: dict | None = None,
    ) -> dict:
        """Counter an existing offer with modified terms.

        Returns a signed NegotiationContract in COUNTER state,
        hash-chained to the original.
        """
        new_pricing = None
        if new_amount is not None:
            new_pricing = {
                **original["pricing"],
                "amount_minor_units": new_amount,
            }

        builder = NegotiationContractBuilder(self._client.signer)
        contract = (
            builder
            .counter(
                previous_contract=original,
                new_pricing=new_pricing,
                new_sla=new_sla,
            )
            .build()
        )
        return contract

    def accept(self, contract: dict) -> dict:
        """Accept an offer or counter-offer.

        Returns a signed NegotiationContract in ACCEPT state.
        """
        builder = NegotiationContractBuilder(self._client.signer)
        return builder.accept(contract)

    def reject(self, contract: dict, reason: str | None = None) -> dict:
        """Reject an offer or counter-offer. Terminal state."""
        builder = NegotiationContractBuilder(self._client.signer)
        return builder.reject(contract, reason=reason)
