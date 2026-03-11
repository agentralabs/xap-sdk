#!/usr/bin/env python3
"""XAP + Stripe Test Mode Demo
============================
Two agents settle a payment through Stripe (test mode).
No real money moves. Uses Stripe test keys.

Requirements:
  pip install xap-sdk stripe
  Set STRIPE_TEST_KEY environment variable

Run: python examples/stripe_test_mode.py
"""

import asyncio
import os

from xap import XAPClient, AgentId
from xap.crypto import XAPSigner


def setup_clients():
    """Set up consumer and provider clients."""
    stripe_key = os.environ.get("STRIPE_TEST_KEY")

    if stripe_key:
        from xap.adapters.stripe_adapter import StripeAdapter
        print(f"Using Stripe test mode (key: {stripe_key[:12]}...)")
        consumer_signer = XAPSigner.generate()
        consumer_id = AgentId.generate()
        adapter = StripeAdapter(api_key=stripe_key)
        consumer = XAPClient(signer=consumer_signer, adapter=adapter, agent_id=consumer_id)
    else:
        print("STRIPE_TEST_KEY not set. Running in mock mode.")
        print("To use real Stripe test API: export STRIPE_TEST_KEY=sk_test_...")
        print()
        from xap.adapters.test_adapter import TestAdapter
        consumer_signer = XAPSigner.generate()
        consumer_id = AgentId.generate()
        adapter = TestAdapter()
        adapter.fund_agent(str(consumer_id), 100_000)
        consumer = XAPClient(signer=consumer_signer, adapter=adapter, agent_id=consumer_id)

    # Provider
    provider_id = AgentId.generate()
    provider = XAPClient.sandbox(agent_id=provider_id, balance=0)
    provider.adapter = consumer.adapter

    return consumer, provider


async def main() -> None:
    consumer, provider = setup_clients()

    # Register provider
    provider_identity = provider.identity(
        display_name="StripeTestProvider",
        capabilities=[{
            "name": "data_processing",
            "version": "1.0.0",
            "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
            "sla": {"max_latency_ms": 3000, "availability_bps": 9900},
        }],
    )
    consumer.discovery.register(provider_identity)
    provider.discovery._registry = consumer.discovery._registry

    # Discovery
    results = consumer.discovery.search(capability="data_processing")
    print(f"Found {len(results['results'])} provider(s)")

    # Negotiate
    offer = consumer.negotiation.create_offer(
        responder=provider.agent_id,
        capability="data_processing",
        amount_minor_units=500,
    )
    accepted = provider.negotiation.accept(offer)
    print(f"Contract accepted: {accepted['negotiation_id']}")

    # Settle
    settlement = consumer.settlement.create_from_contract(
        accepted_contract=accepted,
        payees=[{"agent_id": str(provider.agent_id), "share_bps": 10000, "role": "primary_executor"}],
    )

    settlement = await consumer.settlement.lock(settlement)
    print(f"Funds locked: {settlement['settlement_id']}")
    print(f"  Adapter: {consumer.adapter.adapter_type()}")

    result = await consumer.settlement.verify_and_settle(
        settlement=settlement,
        condition_results=[{
            "condition_id": "cond_0001",
            "type": "deterministic",
            "check": "output_delivered",
            "passed": True,
            "verified_by": "engine",
        }],
    )

    print(f"\nSettlement complete: {result.receipt['outcome']}")
    print(f"Receipt: {result.receipt['receipt_id']}")

    replay_valid = consumer.receipts.verify_replay(result.verity_receipt)
    print(f"Replay verified: {'PASSED' if replay_valid else 'FAILED'}")

    if result.adapter_response:
        trace = result.adapter_response.get("adapter_trace")
        if trace:
            print(f"\nAdapter trace:")
            for k, v in trace.items():
                print(f"  {k}: {v}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
