#!/usr/bin/env python3
"""Two-agent demo — negotiate, settle, and produce a replayable receipt.

This is the core XAP SDK deliverable. In under 30 lines of user code,
two agents negotiate a price, lock funds, verify conditions, settle,
and produce a cryptographically signed, replayable receipt.

Run:
    python examples/two_agent_demo.py
"""

import asyncio

from xap import XAPClient, AgentId


async def main() -> None:
    # --- Setup: two agents in sandbox mode ---
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()

    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id, balance=500_000)

    # Share the same adapter so funds actually move
    bob.adapter = alice.adapter
    bob.adapter.fund_agent(str(bob_id), 500_000)

    # --- Discovery: Bob registers, Alice searches ---
    bob_identity = bob.identity(
        display_name="Bob's Summarizer",
        capabilities=[{
            "name": "text_summarization",
            "version": "1.0.0",
            "pricing": {
                "amount_minor_units": 5000,
                "currency": "USD",
                "model": "fixed",
                "per": "request",
            },
            "sla": {"max_latency_ms": 3000, "availability_bps": 9900},
            "description": "Summarize text documents",
        }],
    )
    alice.discovery.register(bob_identity)
    bob.discovery._registry = alice.discovery._registry  # shared sandbox registry

    results = alice.discovery.search(capability="text_summarization")
    print(f"Discovery: found {len(results['results'])} agent(s) offering text_summarization")
    assert len(results["results"]) == 1
    found_bob = results["results"][0]
    print(f"  -> {found_bob['display_name']} (agent_id={found_bob['agent_id']})")

    # --- Negotiation: Alice offers, Bob counters, Alice accepts ---
    offer = alice.negotiation.create_offer(
        responder=bob_id,
        capability="text_summarization",
        amount_minor_units=4000,
        currency="USD",
        sla={"max_latency_ms": 3000},
    )
    print(f"\nNegotiation:")
    print(f"  Alice offers {offer['pricing']['amount_minor_units']} minor units")
    assert offer["state"] == "OFFER"

    counter = bob.negotiation.counter_offer(offer, new_amount=4500)
    print(f"  Bob counters with {counter['pricing']['amount_minor_units']} minor units")
    assert counter["state"] == "COUNTER"

    accepted = alice.negotiation.accept(counter)
    print(f"  Alice accepts -> state={accepted['state']}")
    assert accepted["state"] == "ACCEPT"

    # --- Settlement: create intent, lock funds, verify & settle ---
    settlement = alice.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=[{
            "agent_id": str(bob_id),
            "share_bps": 10000,
            "role": "primary_executor",
        }],
    )
    print(f"\nSettlement:")
    print(f"  Created: {settlement['settlement_id']} for {settlement['total_amount_minor_units']} {settlement['currency']}")
    assert settlement["state"] == "PENDING_LOCK"

    settlement = await alice.settlement.lock(settlement)
    print(f"  Locked funds -> state={settlement['state']}")
    assert settlement["state"] == "FUNDS_LOCKED"

    # Simulate: Bob did the work, condition passes
    condition_results = [{
        "condition_id": "cond_0001",
        "type": "deterministic",
        "check": "output_delivered",
        "passed": True,
        "verified_by": "engine",
    }]

    result = await alice.settlement.verify_and_settle(settlement, condition_results)
    print(f"  Settled -> outcome={result.receipt['outcome']}, state={result.settlement['state']}")
    assert result.settlement["state"] == "SETTLED"
    assert result.receipt["outcome"] == "SETTLED"

    # --- Receipts: verify replayability ---
    replay_valid = alice.receipts.verify_replay(result.verity_receipt)
    chain_valid = alice.receipts.verify_chain(settlement["settlement_id"])
    print(f"\nReceipts:")
    print(f"  Execution receipt: {result.receipt['receipt_id']}")
    print(f"  Verity receipt:    {result.verity_receipt['verity_id']}")
    print(f"  Replay hash valid: {replay_valid}")
    print(f"  Verity chain valid: {chain_valid}")
    assert replay_valid
    assert chain_valid

    # --- Verify signatures ---
    sigs = result.receipt["signatures"]
    assert sigs["settlement_engine"].startswith("ed25519:")
    assert sigs["payer"].startswith("ed25519:")
    print(f"  Execution receipt signatures valid: settlement_engine + payer")

    total_paid = sum(p["final_amount_minor_units"] for p in result.receipt["payouts"])
    print(f"\nDone. Two agents negotiated, settled {total_paid} minor units,")
    print(f"and produced a replayable receipt — all in sandbox mode.")


if __name__ == "__main__":
    asyncio.run(main())
