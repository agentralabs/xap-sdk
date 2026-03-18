"""End-to-end manifest demo: DECLARE → VERIFY → NEGOTIATE.

Demonstrates the three-step verification handshake from XAP v0.2:

1. DECLARE — Agent publishes a signed AgentManifest
2. VERIFY  — Querying agent verifies the signature and attestations
3. NEGOTIATE — Agents enter NegotiationContract flow with verified trust
"""

from xap import XAPClient, AgentManifest
from xap.verify import verify_manifest


def main():
    # ── Setup: two agents ──────────────────────────────────────────────
    seller = XAPClient.sandbox()
    buyer = XAPClient.sandbox()

    # ── Step 1: DECLARE ────────────────────────────────────────────────
    # Seller builds and signs an AgentManifest
    manifest = seller.manifest.build(
        capabilities=[{
            "name": "code_review",
            "version": "1.0.0",
            "attestation": {
                "total_settlements": 847,
                "success_rate_bps": 9430,
                "dispute_rate_bps": 47,
                "avg_latency_ms": 1240,
                "window_days": 90,
                "receipt_hashes": [],
            },
            "sla": {
                "max_latency_ms": 3000,
                "availability_bps": 9950,
            },
        }],
        economic_terms={
            "accepted_currencies": ["USD", "EUR"],
            "accepted_condition_types": ["deterministic", "probabilistic"],
            "accepted_adapters": ["stripe"],
            "min_amount_minor": 100,
            "max_amount_minor": 1000000,
            "chargeback_policy": "PROPORTIONAL",
            "min_negotiation_rounds": 1,
            "max_concurrent": 50,
        },
        registry_url="https://app.zexrail.com",
    )
    print(f"DECLARE: Manifest {manifest['manifest_id']} signed by {manifest['agent_id']}")
    print(f"  Capabilities: {[c['name'] for c in manifest['capabilities']]}")
    print(f"  Settlements: {manifest['capabilities'][0]['attestation']['total_settlements']}")
    print(f"  Success rate: {manifest['capabilities'][0]['attestation']['success_rate_bps'] / 100}%")

    # ── Step 2: VERIFY ─────────────────────────────────────────────────
    # Buyer verifies the manifest: schema, signature, expiry
    result = verify_manifest(manifest)
    print(f"\nVERIFY: schema={result.schema_valid} sig={result.signature_valid} fresh={result.not_expired}")
    assert result.valid, f"Verification failed: {result.errors}"
    print("  Trust established. Manifest is cryptographically valid.")

    # In production, the buyer would also:
    # - Pick receipt_hashes from attestation
    # - Call verification_endpoint to replay Verity receipts
    # - Confirm claimed success_rate_bps matches replayed outcomes

    # ── Step 3: NEGOTIATE ──────────────────────────────────────────────
    # Buyer enters negotiation with verified trust
    seller_identity = seller.identity(
        display_name="CodeReviewBot",
        capabilities=[{
            "name": "code_review",
            "version": "1.0.0",
            "pricing": {"model": "fixed", "amount_minor_units": 1000, "currency": "USD", "per": "request"},
            "sla": {"max_latency_ms": 3000, "availability_bps": 9950},
        }],
    )

    offer = buyer.negotiation.create_offer(
        responder=seller.agent_id,
        capability="code_review",
        amount_minor_units=1000,
    )
    print(f"\nNEGOTIATE: Offer {offer['negotiation_id']} for code_review at $10.00")

    accepted = seller.negotiation.accept(offer)
    print(f"  Accepted: {accepted['state']}")
    print(f"\nFull handshake complete: DECLARE → VERIFY → NEGOTIATE")


if __name__ == "__main__":
    main()
