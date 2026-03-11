#!/usr/bin/env python3
"""XAP + CrewAI Demo
=================
A CrewAI crew that uses XAP for agent commerce.

Run: python examples/crewai_demo.py
Requires: pip install crewai

This demo works without an LLM by calling tools directly.
"""

import asyncio

from xap import XAPClient
from xap.integrations.crewai import XAPCrewTools


async def main() -> None:
    # Create crew tools (sandbox mode)
    xap_tools = XAPCrewTools.sandbox(balance=100_000)

    # Register a provider
    provider_client = XAPClient.sandbox(balance=0)
    provider_client.adapter = xap_tools.client.adapter
    provider_identity = provider_client.identity(
        display_name="ImageGenerator",
        capabilities=[{
            "name": "image_generation",
            "version": "2.0.0",
            "pricing": {"model": "fixed", "amount_minor_units": 2000, "currency": "USD", "per": "request"},
            "sla": {"max_latency_ms": 10000, "availability_bps": 9800},
        }],
    )
    xap_tools.client.discovery.register(provider_identity)
    provider_client.discovery._registry = xap_tools.client.discovery._registry

    try:
        tools = xap_tools.get_tools()
        print("Available XAP tools for CrewAI:")
        for t in tools:
            print(f"  - {t.name}")
    except ImportError:
        print("CrewAI not installed — running with base integration directly.\n")
        tools = None

    # Run flow using base integration (works with or without CrewAI)
    base = xap_tools

    print("\n--- Discovery ---")
    results = base.discover("image_generation")
    print(f"  Found {len(results['results'])} agent(s)")
    if results["results"]:
        agent = results["results"][0]
        print(f"  -> {agent['display_name']} ({agent['agent_id']})")

    print("\n--- Create Offer ---")
    contract = base.create_offer(str(provider_client.agent_id), "image_generation", 2000)
    print(f"  Offer: {contract['negotiation_id']}, amount={contract['pricing']['amount_minor_units']}")

    print("\n--- Provider Accepts ---")
    accepted = provider_client.negotiation.accept(contract)
    print(f"  state={accepted['state']}")

    print("\n--- Settle ---")
    result = base.settle(accepted)
    print(f"  Outcome: {result['outcome']}")
    print(f"  Receipt: {result['receipt_id']}")
    print(f"  Verity:  {result['verity_id']}")
    print(f"  Replay verified: {result['replay_verified']}")
    print(f"  Total paid: {result['total_paid']} minor units")

    print("\n--- Balances ---")
    buyer_bal = base.check_balance()
    provider_bal = base.check_balance(str(provider_client.agent_id))
    print(f"  Buyer:    {buyer_bal} minor units")
    print(f"  Provider: {provider_bal} minor units")

    print("\nDone. Full XAP flow completed via CrewAI integration.")


if __name__ == "__main__":
    asyncio.run(main())
