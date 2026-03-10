"""XAPClient — the single entry point for the XAP SDK."""

from __future__ import annotations

from xap.types import AgentId
from xap.crypto import XAPSigner
from xap.adapters.base import SettlementAdapter
from xap.adapters.test_adapter import TestAdapter
from xap.builders.identity import AgentIdentityBuilder
from xap.clients.negotiation import NegotiationClient
from xap.clients.settlement import SettlementClient
from xap.clients.receipt import ReceiptClient
from xap.clients.discovery import DiscoveryClient


class XAPClient:
    """The main entry point for the XAP SDK.

    Usage:
        from xap import XAPClient

        client = XAPClient.sandbox()  # test mode with fake money
        # or
        client = XAPClient(signer=my_signer, adapter=my_adapter)
    """

    def __init__(
        self,
        signer: XAPSigner,
        adapter: SettlementAdapter,
        agent_id: AgentId | None = None,
    ) -> None:
        self.signer = signer
        self.adapter = adapter
        self.agent_id = agent_id or AgentId.generate()
        self.negotiation = NegotiationClient(self)
        self.settlement = SettlementClient(self)
        self.receipts = ReceiptClient(self)
        self.discovery = DiscoveryClient(self)

    @classmethod
    def sandbox(
        cls,
        agent_id: AgentId | None = None,
        balance: int = 1_000_000,
    ) -> XAPClient:
        """Create a client in sandbox mode with test adapter and fake money.

        Perfect for development and testing.
        """
        signer = XAPSigner.generate()
        adapter = TestAdapter()
        agent_id = agent_id or AgentId.generate()
        adapter.fund_agent(str(agent_id), balance)
        return cls(signer=signer, adapter=adapter, agent_id=agent_id)

    def identity(
        self,
        display_name: str | None = None,
        capabilities: list[dict] | None = None,
    ) -> dict:
        """Build and return this agent's identity object."""
        builder = AgentIdentityBuilder(self.signer).agent_id(self.agent_id)

        if display_name:
            builder.display_name(display_name)

        for cap in (capabilities or []):
            builder.add_capability(
                name=cap["name"],
                version=cap["version"],
                pricing=cap["pricing"],
                sla=cap["sla"],
                description=cap.get("description"),
            )

        return builder.build()
