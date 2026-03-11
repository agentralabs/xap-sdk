"""XAP tools for LangChain agents.

Usage:
    from xap.integrations.langchain import XAPToolkit
    from langchain.agents import AgentExecutor, create_openai_functions_agent

    toolkit = XAPToolkit.sandbox(balance=100_000)
    tools = toolkit.get_tools()

    # Add to your LangChain agent
    agent = create_openai_functions_agent(llm, tools, prompt)
    executor = AgentExecutor(agent=agent, tools=tools)
"""

from __future__ import annotations

from xap.client import XAPClient
from xap.integrations.base import XAPIntegrationBase


def _require_langchain():
    """Lazy import check for langchain."""
    try:
        from langchain.tools import tool
        return tool
    except ImportError:
        raise ImportError(
            "langchain is required for this integration. "
            "Install it with: pip install langchain"
        )


class XAPToolkit(XAPIntegrationBase):
    """Provides XAP tools for LangChain agents."""

    def __init__(self, client: XAPClient) -> None:
        super().__init__(client)

    @classmethod
    def sandbox(cls, balance: int = 1_000_000) -> XAPToolkit:
        """Create toolkit with sandbox client."""
        client = XAPClient.sandbox(balance=balance)
        return cls(client)

    def get_tools(self) -> list:
        """Return all XAP tools for use with LangChain."""
        return [
            self._discover_tool(),
            self._offer_tool(),
            self._respond_tool(),
            self._settle_tool(),
            self._verify_tool(),
            self._balance_tool(),
        ]

    def _discover_tool(self):
        tool = _require_langchain()
        base = self

        @tool
        def xap_discover_agents(capability: str, min_reputation: int = 0) -> str:
            """Search the XAP registry for agents with specific capabilities.
            Returns matching agents with IDs, capabilities, pricing, and reputation."""
            results = base.discover(capability, min_reputation)
            return base._format_result(results)

        return xap_discover_agents

    def _offer_tool(self):
        tool = _require_langchain()
        base = self

        @tool
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
        tool = _require_langchain()
        base = self

        @tool
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
        tool = _require_langchain()
        base = self

        @tool
        def xap_settle(contract: dict) -> str:
            """Execute a settlement from an accepted negotiation contract.
            Locks funds, verifies conditions, and settles payment.
            Returns settlement result with receipt ID, outcome, and replay status."""
            result = base.settle(contract)
            return base._format_result(result)

        return xap_settle

    def _verify_tool(self):
        tool = _require_langchain()
        base = self

        @tool
        def xap_verify_receipt(verity_receipt: dict) -> str:
            """Verify that a settlement receipt is deterministically replayable.
            Returns whether the replay hash verification passed."""
            valid = base.verify(verity_receipt)
            return base._format_result(valid)

        return xap_verify_receipt

    def _balance_tool(self):
        tool = _require_langchain()
        base = self

        @tool
        def xap_check_balance(agent_id: str = "") -> str:
            """Check an agent's current balance in minor units.
            Leave agent_id empty to check your own balance."""
            aid = agent_id if agent_id else None
            balance = base.check_balance(aid)
            return base._format_result(balance)

        return xap_check_balance
