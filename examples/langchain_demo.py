#!/usr/bin/env python3
"""XAP + LangChain Demo
====================
A LangChain agent that discovers a service provider,
negotiates terms, and settles payment autonomously.

Run: python examples/langchain_demo.py
Requires: pip install langchain langchain-openai

This demo works without an LLM by calling tools directly.
"""

import asyncio
import json

from xap import XAPClient
from xap.integrations.langchain import XAPToolkit


async def main() -> None:
    # Create toolkit (sandbox mode, no real money)
    toolkit = XAPToolkit.sandbox(balance=100_000)

    # Register a provider in the sandbox registry
    provider_client = XAPClient.sandbox(balance=0)
    provider_client.adapter = toolkit.client.adapter
    provider_identity = provider_client.identity(
        display_name="DataAnalyzer",
        capabilities=[{
            "name": "data_analysis",
            "version": "1.0.0",
            "pricing": {"model": "fixed", "amount_minor_units": 1000, "currency": "USD", "per": "request"},
            "sla": {"max_latency_ms": 5000, "availability_bps": 9900},
        }],
    )
    toolkit.client.discovery.register(provider_identity)
    provider_client.discovery._registry = toolkit.client.discovery._registry

    try:
        tools = toolkit.get_tools()
    except ImportError:
        print("LangChain not installed — running with base integration directly.\n")
        _run_without_langchain(toolkit, provider_client)
        return

    print("Available XAP tools for LangChain:")
    for t in tools:
        print(f"  - {t.name}: {t.description}")

    # --- Discovery ---
    print("\n--- Discovery ---")
    result = tools[0].invoke({"capability": "data_analysis"})
    print(result)
    discovery_data = json.loads(result)

    # --- Create Offer ---
    print("\n--- Create Offer ---")
    result = tools[1].invoke({
        "agent_id": str(provider_client.agent_id),
        "capability": "data_analysis",
        "amount": 1000,
    })
    print(result)
    offer_data = json.loads(result)
    contract = offer_data["contract"]

    # --- Accept Offer (provider side) ---
    print("\n--- Accept Offer ---")
    accepted = provider_client.negotiation.accept(contract)
    print(f"  Provider accepted: state={accepted['state']}")

    # --- Settle ---
    print("\n--- Settle ---")
    result = tools[3].invoke({"contract": accepted})
    print(result)

    # --- Check Balance ---
    print("\n--- Check Balance ---")
    result = tools[5].invoke({"agent_id": ""})
    print(f"  Buyer balance: {result}")

    print("\nDone. Full XAP flow completed via LangChain tools.")


def _run_without_langchain(toolkit: XAPToolkit, provider_client: XAPClient) -> None:
    """Fallback: run the flow using the base integration directly."""
    base = toolkit

    print("--- Discovery ---")
    results = base.discover("data_analysis")
    print(f"  Found {len(results['results'])} agent(s)")

    print("\n--- Create Offer ---")
    contract = base.create_offer(str(provider_client.agent_id), "data_analysis", 1000)
    print(f"  Offer created: {contract['negotiation_id']}, state={contract['state']}")

    print("\n--- Accept Offer ---")
    accepted = provider_client.negotiation.accept(contract)
    print(f"  Provider accepted: state={accepted['state']}")

    print("\n--- Settle ---")
    result = base.settle(accepted)
    print(f"  Outcome: {result['outcome']}")
    print(f"  Receipt: {result['receipt_id']}")
    print(f"  Replay verified: {result['replay_verified']}")
    print(f"  Total paid: {result['total_paid']} minor units")

    print("\n--- Check Balance ---")
    balance = base.check_balance()
    print(f"  Buyer balance: {balance} minor units")

    print("\nDone. Full XAP flow completed via base integration.")


if __name__ == "__main__":
    asyncio.run(main())
