#!/usr/bin/env python3
"""Unknown outcome — partial and refund scenarios.

Demonstrates what happens when conditions fail partially or fully:
- Partial: some conditions pass -> pro-rata payout
- Refund: all conditions fail -> full refund to payer

Run:
    python examples/unknown_outcome.py
"""

import asyncio

from xap import XAPClient, AgentId


async def run_scenario(name: str, condition_results: list[dict]) -> None:
    alice_id = AgentId.generate()
    bob_id = AgentId.generate()
    alice = XAPClient.sandbox(agent_id=alice_id, balance=1_000_000)
    bob = XAPClient.sandbox(agent_id=bob_id)
    bob.adapter = alice.adapter

    offer = alice.negotiation.create_offer(
        responder=bob_id,
        capability="image_generation",
        amount_minor_units=10000,
    )
    accepted = bob.negotiation.accept(offer)

    settlement = alice.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=[{"agent_id": str(bob_id), "share_bps": 10000}],
        conditions=[
            {"condition_id": "cond_aa01", "type": "probabilistic", "check": "quality_score", "verifier": "engine", "required": True, "operator": "gte", "threshold": 8000},
            {"condition_id": "cond_bb02", "type": "deterministic", "check": "output_delivered", "verifier": "engine", "required": True},
        ],
    )

    settlement = await alice.settlement.lock(settlement)
    result = await alice.settlement.verify_and_settle(settlement, condition_results)

    print(f"\n--- {name} ---")
    print(f"  Outcome: {result.receipt['outcome']}")
    print(f"  State:   {result.settlement['state']}")
    print(f"  Payouts: {len(result.receipt['payouts'])}")
    for p in result.receipt["payouts"]:
        print(f"    {p['agent_id']}: {p['final_amount_minor_units']} minor units")

    replay_ok = alice.receipts.verify_replay(result.verity_receipt)
    print(f"  Replay valid: {replay_ok}")
    assert replay_ok


async def main() -> None:
    print("=== Unknown Outcome Scenarios ===")

    # Scenario 1: Partial — quality fails, delivery passes
    await run_scenario("PARTIAL (1/2 conditions pass)", [
        {"condition_id": "cond_aa01", "type": "probabilistic", "check": "quality_score",
         "passed": False, "confidence_bps": 4500, "actual_value": 4500, "threshold": 8000, "operator": "gte"},
        {"condition_id": "cond_bb02", "type": "deterministic", "check": "output_delivered",
         "passed": True},
    ])

    # Scenario 2: Full refund — both fail
    await run_scenario("REFUNDED (0/2 conditions pass)", [
        {"condition_id": "cond_aa01", "type": "probabilistic", "check": "quality_score",
         "passed": False, "confidence_bps": 2000},
        {"condition_id": "cond_bb02", "type": "deterministic", "check": "output_delivered",
         "passed": False},
    ])

    # Scenario 3: All pass
    await run_scenario("SETTLED (2/2 conditions pass)", [
        {"condition_id": "cond_aa01", "type": "probabilistic", "check": "quality_score",
         "passed": True, "confidence_bps": 9500},
        {"condition_id": "cond_bb02", "type": "deterministic", "check": "output_delivered",
         "passed": True},
    ])

    print("\nAll scenarios completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
