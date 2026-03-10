"""Integration tests — full end-to-end flows through the SDK."""

import pytest

from xap import XAPClient, AgentId
from xap.clients.settlement import SettlementResult


@pytest.mark.asyncio
async def test_full_two_agent_flow():
    """Complete negotiate -> settle -> receipt flow between two agents."""
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()
    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id)
    bob.adapter = alice.adapter

    # Negotiate
    offer = alice.negotiation.create_offer(
        responder=bob_id, capability="summarize",
        amount_minor_units=5000, currency="USD",
    )
    counter = bob.negotiation.counter_offer(offer, new_amount=4000)
    accepted = alice.negotiation.accept(counter)
    assert accepted["state"] == "ACCEPT"
    assert accepted["pricing"]["amount_minor_units"] == 4000

    # Settle
    settlement = alice.settlement.create_from_contract(
        accepted, payees=[{"agent_id": str(bob_id), "share_bps": 10000}],
    )
    settlement = await alice.settlement.lock(settlement)
    result = await alice.settlement.verify_and_settle(
        settlement, [{"condition_id": "cond_0001", "check": "output_delivered", "passed": True}],
    )

    assert isinstance(result, SettlementResult)
    assert result.settlement["state"] == "SETTLED"
    assert result.receipt["outcome"] == "SETTLED"

    # Verify receipts
    assert alice.receipts.verify_replay(result.verity_receipt)
    assert alice.receipts.verify_chain(settlement["settlement_id"])

    # Verify signatures present
    sigs = result.receipt["signatures"]
    assert sigs["settlement_engine"].startswith("ed25519:")
    assert sigs["payer"].startswith("ed25519:")


@pytest.mark.asyncio
async def test_three_agent_split_flow():
    """Settlement split between two payees."""
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()
    carol_id = AgentId.generate()
    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id)
    carol = XAPClient.sandbox(agent_id=carol_id)
    bob.adapter = alice.adapter
    carol.adapter = alice.adapter

    offer = alice.negotiation.create_offer(
        responder=bob_id, capability="analysis",
        amount_minor_units=10000,
    )
    accepted = bob.negotiation.accept(offer)

    settlement = alice.settlement.create_from_contract(
        accepted,
        payees=[
            {"agent_id": str(bob_id), "share_bps": 6000, "role": "primary_executor"},
            {"agent_id": str(carol_id), "share_bps": 4000, "role": "data_provider"},
        ],
    )
    settlement = await alice.settlement.lock(settlement)
    result = await alice.settlement.verify_and_settle(
        settlement, [{"condition_id": "cond_0001", "check": "done", "passed": True}],
    )

    assert result.settlement["state"] == "SETTLED"
    payouts = result.receipt["payouts"]
    bob_payout = next(p for p in payouts if p["agent_id"] == str(bob_id))
    carol_payout = next(p for p in payouts if p["agent_id"] == str(carol_id))
    assert bob_payout["final_amount_minor_units"] == 6000
    assert carol_payout["final_amount_minor_units"] == 4000


@pytest.mark.asyncio
async def test_partial_settlement_pro_rata():
    """Partial conditions pass -> pro-rata payout."""
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()
    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id)
    bob.adapter = alice.adapter

    offer = alice.negotiation.create_offer(
        responder=bob_id, capability="test", amount_minor_units=10000,
    )
    accepted = bob.negotiation.accept(offer)

    settlement = alice.settlement.create_from_contract(
        accepted, payees=[{"agent_id": str(bob_id), "share_bps": 10000}],
        conditions=[
            {"condition_id": "cond_0001", "type": "deterministic", "check": "a", "verifier": "engine", "required": True},
            {"condition_id": "cond_0002", "type": "deterministic", "check": "b", "verifier": "engine", "required": True},
        ],
    )
    settlement = await alice.settlement.lock(settlement)
    result = await alice.settlement.verify_and_settle(
        settlement,
        [
            {"condition_id": "cond_0001", "check": "a", "passed": True},
            {"condition_id": "cond_0002", "check": "b", "passed": False},
        ],
    )

    assert result.settlement["state"] == "PARTIAL"
    assert result.receipt["outcome"] == "PARTIAL"
    # 1/2 conditions passed -> 50% payout = 5000
    bob_payout = result.receipt["payouts"][0]
    assert bob_payout["final_amount_minor_units"] == 5000


@pytest.mark.asyncio
async def test_full_refund_all_conditions_fail():
    """All conditions fail -> full refund."""
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()
    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id)
    bob.adapter = alice.adapter

    offer = alice.negotiation.create_offer(
        responder=bob_id, capability="test", amount_minor_units=10000,
    )
    accepted = bob.negotiation.accept(offer)

    settlement = alice.settlement.create_from_contract(
        accepted, payees=[{"agent_id": str(bob_id), "share_bps": 10000}],
    )
    settlement = await alice.settlement.lock(settlement)
    result = await alice.settlement.verify_and_settle(
        settlement, [{"condition_id": "cond_0001", "check": "done", "passed": False}],
    )

    assert result.settlement["state"] == "REFUNDED"
    assert result.receipt["outcome"] == "REFUNDED"
    assert len(result.receipt["payouts"]) == 0


@pytest.mark.asyncio
async def test_discovery_register_and_search():
    """Register agents and search by capability."""
    alice = XAPClient.sandbox()
    bob_id = AgentId.generate()
    bob = XAPClient.sandbox(agent_id=bob_id)

    bob_identity = bob.identity(
        display_name="Bob",
        capabilities=[{
            "name": "translate",
            "version": "2.0.0",
            "pricing": {"amount_minor_units": 200, "currency": "USD", "model": "fixed", "per": "request"},
            "sla": {"max_latency_ms": 1000, "availability_bps": 9900},
        }],
    )
    alice.discovery.register(bob_identity)

    results = alice.discovery.search(capability="translate")
    assert len(results["results"]) == 1
    assert results["results"][0]["agent_id"] == str(bob_id)

    results = alice.discovery.search(capability="nonexistent")
    assert len(results["results"]) == 0


@pytest.mark.asyncio
async def test_receipt_signature_valid():
    """Execution receipt signature is cryptographically valid."""
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

    sigs = result.receipt["signatures"]
    assert sigs["settlement_engine"].startswith("ed25519:")
    assert sigs["payer"].startswith("ed25519:")


@pytest.mark.asyncio
async def test_verity_receipt_has_replay_hash():
    """Verity receipt contains a valid replay hash."""
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

    vr = result.verity_receipt
    assert "replay_hash" in vr
    assert vr["replay_hash"].startswith("sha256:")
    assert alice.receipts.verify_replay(vr)
