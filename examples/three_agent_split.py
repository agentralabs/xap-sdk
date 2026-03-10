#!/usr/bin/env python3
"""Three-agent split — settlement with multiple payees.

Demonstrates a payer (Alice) splitting payment between two service
providers (Bob 70%, Carol 30%) with proportional payouts.

Run:
    python examples/three_agent_split.py
"""

import asyncio

from xap import XAPClient, AgentId


async def main() -> None:
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()
    carol_id = AgentId.generate()

    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id)
    carol = XAPClient.sandbox(agent_id=carol_id)

    # Shared adapter
    bob.adapter = alice.adapter
    carol.adapter = alice.adapter

    # Alice negotiates with Bob (primary)
    offer = alice.negotiation.create_offer(
        responder=bob_id,
        capability="data_analysis",
        amount_minor_units=10000,
        currency="USD",
    )
    accepted = bob.negotiation.accept(offer)

    # Settlement with two payees: Bob 70%, Carol 30%
    settlement = alice.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=[
            {"agent_id": str(bob_id), "share_bps": 7000, "role": "primary_executor"},
            {"agent_id": str(carol_id), "share_bps": 3000, "role": "data_provider"},
        ],
    )
    print(f"Settlement: {settlement['settlement_id']}")
    print(f"  Total: {settlement['total_amount_minor_units']} {settlement['currency']}")
    print(f"  Payees: {len(settlement['payee_agents'])}")

    settlement = await alice.settlement.lock(settlement)

    result = await alice.settlement.verify_and_settle(
        settlement,
        [{"condition_id": "cond_0001", "check": "output_delivered", "passed": True}],
    )

    print(f"\nOutcome: {result.receipt['outcome']}")
    for payout in result.receipt["payouts"]:
        print(f"  {payout['agent_id']}: {payout['final_amount_minor_units']} {payout['currency']} ({payout['role']})")

    # Verify: Bob gets 7000, Carol gets 3000
    bob_payout = next(p for p in result.receipt["payouts"] if p["agent_id"] == str(bob_id))
    carol_payout = next(p for p in result.receipt["payouts"] if p["agent_id"] == str(carol_id))
    assert bob_payout["final_amount_minor_units"] == 7000
    assert carol_payout["final_amount_minor_units"] == 3000
    print("\nAll assertions passed.")


if __name__ == "__main__":
    asyncio.run(main())
