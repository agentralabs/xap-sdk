"""Tests for the high-level client modules."""

import pytest

from xap import XAPClient, AgentId, XAPStateError, XAPError


def _aid(name: str = "test") -> AgentId:
    """Generate a valid AgentId."""
    return AgentId.generate()


def _cap(name: str = "test_cap", amount: int = 1000) -> dict:
    return {
        "name": name,
        "version": "1.0.0",
        "pricing": {"amount_minor_units": amount, "currency": "USD", "model": "fixed", "per": "request"},
        "sla": {"max_latency_ms": 1000, "availability_bps": 9900},
    }


class TestXAPClient:
    def test_sandbox_creates_funded_client(self):
        client = XAPClient.sandbox(balance=500_000)
        assert client.signer is not None
        assert client.agent_id is not None
        assert client.adapter is not None
        bal = client.adapter.balance(str(client.agent_id))
        assert bal == 500_000

    def test_sandbox_with_custom_agent_id(self):
        aid = AgentId.generate()
        client = XAPClient.sandbox(agent_id=aid)
        assert client.agent_id == aid

    def test_identity_with_capabilities(self):
        client = XAPClient.sandbox()
        identity = client.identity(
            display_name="CapBot",
            capabilities=[_cap("summarize", 100)],
        )
        assert len(identity["capabilities"]) == 1
        assert identity["capabilities"][0]["name"] == "summarize"

    def test_sub_clients_attached(self):
        client = XAPClient.sandbox()
        assert client.negotiation is not None
        assert client.settlement is not None
        assert client.receipts is not None
        assert client.discovery is not None


class TestNegotiationClient:
    def setup_method(self):
        self.alice_id = AgentId.generate()
        self.bob_id = AgentId.generate()
        self.alice = XAPClient.sandbox(agent_id=self.alice_id)
        self.bob = XAPClient.sandbox(agent_id=self.bob_id)

    def test_create_offer(self):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id,
            capability="test_cap",
            amount_minor_units=1000,
        )
        assert offer["state"] == "OFFER"
        assert offer["pricing"]["amount_minor_units"] == 1000

    def test_counter_offer(self):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id, capability="test_cap", amount_minor_units=1000,
        )
        counter = self.bob.negotiation.counter_offer(offer, new_amount=800)
        assert counter["state"] == "COUNTER"
        assert counter["pricing"]["amount_minor_units"] == 800

    def test_accept(self):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id, capability="test_cap", amount_minor_units=1000,
        )
        accepted = self.bob.negotiation.accept(offer)
        assert accepted["state"] == "ACCEPT"

    def test_reject(self):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id, capability="test_cap", amount_minor_units=1000,
        )
        rejected = self.bob.negotiation.reject(offer, reason="too expensive")
        assert rejected["state"] == "REJECT"

    def test_full_negotiation_flow(self):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id, capability="translate", amount_minor_units=5000,
            currency="EUR", sla={"max_latency_ms": 2000},
        )
        counter = self.bob.negotiation.counter_offer(offer, new_amount=4000)
        accepted = self.alice.negotiation.accept(counter)
        assert accepted["state"] == "ACCEPT"
        assert accepted["pricing"]["amount_minor_units"] == 4000


class TestSettlementClient:
    def setup_method(self):
        self.alice_id = AgentId.generate()
        self.bob_id = AgentId.generate()
        self.alice = XAPClient.sandbox(agent_id=self.alice_id, balance=1_000_000)
        self.bob = XAPClient.sandbox(agent_id=self.bob_id)
        self.bob.adapter = self.alice.adapter

    def _make_accepted_contract(self, amount=5000):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id, capability="test", amount_minor_units=amount,
        )
        return self.bob.negotiation.accept(offer)

    def test_create_from_contract(self):
        accepted = self._make_accepted_contract()
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        assert settlement["state"] == "PENDING_LOCK"
        assert settlement["total_amount_minor_units"] == 5000

    def test_create_from_non_accepted_contract_fails(self):
        offer = self.alice.negotiation.create_offer(
            responder=self.bob_id, capability="test", amount_minor_units=5000,
        )
        with pytest.raises(XAPStateError):
            self.alice.settlement.create_from_contract(
                offer, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
            )

    def test_shares_must_sum_to_10000(self):
        accepted = self._make_accepted_contract()
        with pytest.raises(XAPError):
            self.alice.settlement.create_from_contract(
                accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 5000}],
            )

    @pytest.mark.asyncio
    async def test_lock(self):
        accepted = self._make_accepted_contract()
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        locked = await self.alice.settlement.lock(settlement)
        assert locked["state"] == "FUNDS_LOCKED"

    @pytest.mark.asyncio
    async def test_lock_wrong_state_fails(self):
        accepted = self._make_accepted_contract()
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        locked = await self.alice.settlement.lock(settlement)
        with pytest.raises(XAPStateError):
            await self.alice.settlement.lock(locked)

    @pytest.mark.asyncio
    async def test_verify_and_settle_all_pass(self):
        accepted = self._make_accepted_contract(10000)
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        settlement = await self.alice.settlement.lock(settlement)
        result = await self.alice.settlement.verify_and_settle(
            settlement, [{"condition_id": "cond_0001", "check": "output_delivered", "passed": True}],
        )
        assert result.settlement["state"] == "SETTLED"
        assert result.receipt["outcome"] == "SETTLED"

    @pytest.mark.asyncio
    async def test_verify_and_settle_partial(self):
        accepted = self._make_accepted_contract(10000)
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        settlement = await self.alice.settlement.lock(settlement)
        result = await self.alice.settlement.verify_and_settle(
            settlement,
            [
                {"condition_id": "cond_0001", "check": "quality", "passed": True},
                {"condition_id": "cond_0002", "check": "speed", "passed": False},
            ],
        )
        assert result.settlement["state"] == "PARTIAL"
        assert result.receipt["outcome"] == "PARTIAL"

    @pytest.mark.asyncio
    async def test_verify_and_settle_refund(self):
        accepted = self._make_accepted_contract(10000)
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        settlement = await self.alice.settlement.lock(settlement)
        result = await self.alice.settlement.verify_and_settle(
            settlement, [{"condition_id": "cond_0001", "check": "output", "passed": False}],
        )
        assert result.settlement["state"] == "REFUNDED"
        assert result.receipt["outcome"] == "REFUNDED"

    @pytest.mark.asyncio
    async def test_refund(self):
        accepted = self._make_accepted_contract()
        settlement = self.alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(self.bob_id), "share_bps": 10000}],
        )
        settlement = await self.alice.settlement.lock(settlement)
        refunded = await self.alice.settlement.refund(settlement, reason="cancelled")
        assert refunded["state"] == "REFUNDED"


class TestDiscoveryClient:
    def test_register_and_search(self):
        client = XAPClient.sandbox()
        identity = client.identity(
            display_name="SearchBot",
            capabilities=[_cap("search", 100)],
        )
        client.discovery.register(identity)
        results = client.discovery.search(capability="search")
        assert len(results["results"]) == 1
        assert results["results"][0]["agent_id"] == str(client.agent_id)

    def test_search_no_match(self):
        client = XAPClient.sandbox()
        results = client.discovery.search(capability="nonexistent")
        assert len(results["results"]) == 0

    def test_search_with_filters(self):
        client = XAPClient.sandbox()
        identity = client.identity(
            display_name="ExpensiveBot",
            capabilities=[_cap("premium", 50000)],
        )
        client.discovery.register(identity)
        # Price filter should exclude
        results = client.discovery.search(capability="premium", max_price_minor_units=1000)
        assert len(results["results"]) == 0
        # No price filter should include
        results = client.discovery.search(capability="premium")
        assert len(results["results"]) == 1


class TestReceiptClient:
    @pytest.mark.asyncio
    async def test_replay_hash_verification(self):
        alice_id = AgentId.generate()
        bob_id = AgentId.generate()
        alice = XAPClient.sandbox(agent_id=alice_id, balance=100_000)
        bob = XAPClient.sandbox(agent_id=bob_id)
        bob.adapter = alice.adapter

        offer = alice.negotiation.create_offer(
            responder=bob_id, capability="test", amount_minor_units=1000,
        )
        accepted = bob.negotiation.accept(offer)
        settlement = alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(bob_id), "share_bps": 10000}],
        )
        settlement = await alice.settlement.lock(settlement)
        result = await alice.settlement.verify_and_settle(
            settlement, [{"condition_id": "cond_0001", "check": "done", "passed": True}],
        )
        assert alice.receipts.verify_replay(result.verity_receipt)

    @pytest.mark.asyncio
    async def test_verity_chain_integrity(self):
        alice_id = AgentId.generate()
        bob_id = AgentId.generate()
        alice = XAPClient.sandbox(agent_id=alice_id, balance=100_000)
        bob = XAPClient.sandbox(agent_id=bob_id)
        bob.adapter = alice.adapter

        offer = alice.negotiation.create_offer(
            responder=bob_id, capability="test", amount_minor_units=1000,
        )
        accepted = bob.negotiation.accept(offer)
        settlement = alice.settlement.create_from_contract(
            accepted, payees=[{"agent_id": str(bob_id), "share_bps": 10000}],
        )
        settlement = await alice.settlement.lock(settlement)
        result = await alice.settlement.verify_and_settle(
            settlement, [{"condition_id": "cond_0001", "check": "done", "passed": True}],
        )
        assert alice.receipts.verify_chain(settlement["settlement_id"])
