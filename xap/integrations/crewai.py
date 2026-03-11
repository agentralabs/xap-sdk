"""XAP tools for CrewAI agents.

Usage:
    from xap.integrations.crewai import XAPCrewTools
    from crewai import Agent, Task, Crew

    xap_tools = XAPCrewTools.sandbox(balance=100_000)

    agent = Agent(
        role="Payment Negotiator",
        goal="Find the best service provider and negotiate terms",
        tools=xap_tools.get_tools(),
    )
"""

from __future__ import annotations

from xap.client import XAPClient
from xap.integrations.base import XAPIntegrationBase


def _require_crewai():
    """Lazy import check for crewai."""
    try:
        from crewai.tools import tool
        return tool
    except ImportError:
        try:
            from crewai_tools import tool
            return tool
        except ImportError:
            raise ImportError(
                "crewai is required for this integration. "
                "Install it with: pip install crewai"
            )


class XAPCrewTools(XAPIntegrationBase):
    """Provides XAP tools for CrewAI agents."""

    def __init__(self, client: XAPClient) -> None:
        super().__init__(client)

    @classmethod
    def sandbox(cls, balance: int = 1_000_000) -> XAPCrewTools:
        """Create crew tools with sandbox client."""
        client = XAPClient.sandbox(balance=balance)
        return cls(client)

    def get_tools(self) -> list:
        """Return all XAP tools for use with CrewAI."""
        return [
            self._discover_tool(),
            self._offer_tool(),
            self._respond_tool(),
            self._settle_tool(),
            self._verify_tool(),
            self._balance_tool(),
        ]

    def _discover_tool(self):
        tool = _require_crewai()
        base = self

        @tool("XAP Discover Agents")
        def xap_discover_agents(capability: str, min_reputation: int = 0) -> str:
            """Search the XAP registry for agents with specific capabilities.
            Returns matching agents with IDs, capabilities, pricing, and reputation."""
            results = base.discover(capability, min_reputation)
            return base._format_result(results)

        return xap_discover_agents

    def _offer_tool(self):
        tool = _require_crewai()
        base = self

        @tool("XAP Create Offer")
        def xap_create_offer(agent_id: str, capability: str, amount: int) -> str:
            """Create a negotiation offer to an agent for a service.
            Amount is in minor units (e.g. 500 = $5.00 USD)."""
            contract = base.create_offer(agent_id, capability, amount)
            return base._format_result({
                "negotiation_id": contract["negotiation_id"],
                "state": contract["state"],
                "amount": contract["pricing"]["amount_minor_units"],
                "currency": contract["pricing"]["currency"],
                "contract": contract,
            })

        return xap_create_offer

    def _respond_tool(self):
        tool = _require_crewai()
        base = self

        @tool("XAP Respond to Offer")
        def xap_respond_to_offer(contract: dict, action: str, new_amount: int = None) -> str:
            """Accept, reject, or counter a negotiation offer.
            Action must be 'accept', 'reject', or 'counter'.
            If countering, provide new_amount in minor units."""
            result = base.respond_to_offer(contract, action, new_amount=new_amount)
            return base._format_result({
                "negotiation_id": result["negotiation_id"],
                "state": result["state"],
                "contract": result,
            })

        return xap_respond_to_offer

    def _settle_tool(self):
        tool = _require_crewai()
        base = self

        @tool("XAP Settle")
        def xap_settle(contract: dict) -> str:
            """Execute a settlement from an accepted negotiation contract.
            Locks funds, verifies conditions, and settles payment.
            Returns settlement result with receipt ID, outcome, and replay status."""
            result = base.settle(contract)
            return base._format_result(result)

        return xap_settle

    def _verify_tool(self):
        tool = _require_crewai()
        base = self

        @tool("XAP Verify Receipt")
        def xap_verify_receipt(verity_receipt: dict) -> str:
            """Verify that a settlement receipt is deterministically replayable.
            Returns whether the replay hash verification passed."""
            valid = base.verify(verity_receipt)
            return base._format_result(valid)

        return xap_verify_receipt

    def _balance_tool(self):
        tool = _require_crewai()
        base = self

        @tool("XAP Check Balance")
        def xap_check_balance(agent_id: str = "") -> str:
            """Check an agent's current balance in minor units.
            Leave agent_id empty to check your own balance."""
            aid = agent_id if agent_id else None
            balance = base.check_balance(aid)
            return base._format_result(balance)

        return xap_check_balance
