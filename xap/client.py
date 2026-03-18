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
from xap.manifest import AgentManifest


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

    @property
    def manifest(self) -> AgentManifestAccessor:
        """Access the AgentManifest builder and verifier."""
        return AgentManifestAccessor(self)

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


class AgentManifestAccessor:
    """Provides manifest operations through XAPClient.manifest."""

    def __init__(self, client: XAPClient) -> None:
        self._client = client

    def build(
        self,
        capabilities: list[dict],
        economic_terms: dict,
        **kwargs,
    ) -> dict:
        """Build and sign an AgentManifest for this client's agent."""
        return AgentManifest.build(
            agent_id=str(self._client.agent_id),
            signer=self._client.signer,
            capabilities=capabilities,
            economic_terms=economic_terms,
            **kwargs,
        )

    @staticmethod
    def verify(manifest: dict) -> bool:
        """Verify an AgentManifest signature."""
        return AgentManifest.verify(manifest)

    @staticmethod
    def is_expired(manifest: dict) -> bool:
        """Check if a manifest has expired."""
        return AgentManifest.is_expired(manifest)
